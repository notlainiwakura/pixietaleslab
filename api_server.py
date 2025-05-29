from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional
from book_generator import BookCreationWorkflow, StoryGeneratorAgent, CoherenceAgent, BookAssemblerAgent, IllustrationGeneratorAgent, StoryElementsAgent
import os
import tempfile
import uuid
from google.cloud import firestore, storage

app = FastAPI()

# Allow frontend to access the API (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Firestore session helpers

db = firestore.Client()
SESSION_COLLECTION = "sessions"

def save_session(session_id, data):
    db.collection(SESSION_COLLECTION).document(session_id).set(data)

def get_session(session_id):
    doc = db.collection(SESSION_COLLECTION).document(session_id).get()
    return doc.to_dict() if doc.exists else None

def delete_session(session_id):
    db.collection(SESSION_COLLECTION).document(session_id).delete()

class BookRequest(BaseModel):
    randomize_all: bool = False
    character_name: Optional[str] = None
    animal: Optional[str] = None
    gender: Optional[str] = None
    custom_elements: Optional[str] = None
    setting: Optional[str] = None

@app.post("/api/generate-story")
async def generate_story(req: BookRequest):
    params = {"randomize_all": req.randomize_all}
    if req.character_name: params["character_name"] = req.character_name
    if req.animal: params["animal"] = req.animal
    if req.gender: params["gender"] = req.gender
    if req.custom_elements: params["custom_elements"] = req.custom_elements
    if req.setting: params["setting"] = req.setting

    # Generate story
    memory = {}
    processed = BookCreationWorkflow().sub_agents[0].run(params, memory=memory)
    story = StoryGeneratorAgent(name="StoryGeneratorAgent").run(processed, memory=memory)
    elements = StoryElementsAgent(name="StoryElementsAgent").run(story, memory=memory)
    session_id = str(uuid.uuid4())
    # Only generate narration (not the whole book)
    save_session(session_id, {
        "params": processed,
        "story": story,
        "elements": elements,
    })
    return {
        "session_id": session_id,
        "story": story,
        "elements": elements,
    }

GCS_BUCKET_NAME = "pixietales-books"
storage_client = storage.Client()
bucket = storage_client.bucket(GCS_BUCKET_NAME)

def upload_file_to_gcs(local_path, gcs_path):
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_path)
    blob.make_public()
    return blob.public_url

def upload_illustrations_to_gcs(illustration_paths, session_id):
    gcs_urls = []
    for i, img_path in enumerate(illustration_paths):
        gcs_img_path = f"books/{session_id}/illustration_{i}.png"
        url = upload_file_to_gcs(img_path, gcs_img_path)
        gcs_urls.append(url)
    return gcs_urls

def cleanup_local_files(file_paths):
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"Failed to delete {path}: {e}")

@app.post("/api/generate-book")
async def generate_book(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    session_id = data.get("session_id")
    session = get_session(session_id)
    if not session:
        return {"error": "Session not found"}
    # Set status to pending
    session["status"] = "pending"
    save_session(session_id, session)
    # Start background book generation
    background_tasks.add_task(run_book_generation, session_id)
    return {"session_id": session_id, "status": "pending"}

def run_book_generation(session_id):
    session = get_session(session_id)
    if not session:
        return
    try:
        params = session["params"]
        story = session["story"]
        memory = {"story": story}
        prompts = CoherenceAgent(name="CoherenceAgent").run(story, params, memory=memory)
        illustrations = IllustrationGeneratorAgent(name="IllustrationGeneratorAgent").run(
            prompts, None, memory=memory
        )
        scenes = memory["scenes"] if "scenes" in memory else [story]
        artifact = {}
        BookAssemblerAgent(name="BookAssemblerAgent").run(scenes, illustrations, artifact=artifact)
        book_filename = "PixieLabs Book.pdf"
        pdf_path = os.path.join(tempfile.gettempdir(), book_filename)
        gcs_pdf_path = f"books/{session_id}/{book_filename}"
        pdf_url = upload_file_to_gcs(pdf_path, gcs_pdf_path)
        gcs_illustration_urls = upload_illustrations_to_gcs(illustrations, session_id)
        cleanup_local_files([pdf_path] + illustrations)
        session["book_filename"] = book_filename
        session["illustration_paths"] = illustrations
        session["pdf_url"] = pdf_url
        session["illustration_urls"] = gcs_illustration_urls
        session["status"] = "done"
        save_session(session_id, session)
    except Exception as e:
        session["status"] = "error"
        session["error_message"] = str(e)
        save_session(session_id, session)

@app.get("/api/book-status")
def book_status(session_id: str):
    session = get_session(session_id)
    if not session:
        return {"error": "Session not found"}
    status = session.get("status", "pending")
    if status == "done":
        return {
            "status": "done",
            "book": f"/api/download-book?session_id={session_id}",
            "book_filename": session.get("book_filename"),
            "illustrations": session.get("illustration_urls"),
            "pdf_url": session.get("pdf_url"),
            "scenes": session.get("scenes"),
        }
    elif status == "error":
        return {"status": "error", "error": session.get("error_message", "Unknown error")}
    else:
        return {"status": status}

@app.get("/api/download-book")
def download_book(session_id: str):
    session = get_session(session_id)
    if not session:
        return {"error": "Session not found"}
    if "pdf_url" not in session:
        return {"error": "PDF not found"}
    return RedirectResponse(session["pdf_url"]) 