from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from book_generator import BookCreationWorkflow, StoryGeneratorAgent, CoherenceAgent, BookAssemblerAgent, IllustrationGeneratorAgent, StoryElementsAgent
import os
import tempfile
import uuid

app = FastAPI()

# Allow frontend to access the API (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for session data (MVP, not for production)
session_store = {}

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
    session_store[session_id] = {
        "params": processed,
        "story": story,
        "elements": elements,
    }
    return {
        "session_id": session_id,
        "story": story,
        "elements": elements,
    }

@app.post("/api/generate-book")
async def generate_book(request: Request):
    data = await request.json()
    session_id = data.get("session_id")
    session = session_store.get(session_id)
    if not session:
        return {"error": "Session not found"}
    params = session["params"]
    story = session["story"]
    memory = {"story": story}
    # Continue with illustration and PDF generation
    prompts = CoherenceAgent(name="CoherenceAgent").run(story, params, memory=memory)
    illustrations = IllustrationGeneratorAgent(name="IllustrationGeneratorAgent").run(
        prompts, None, memory=memory
    )
    scenes = memory["scenes"] if "scenes" in memory else [story]
    result = BookAssemblerAgent(name="BookAssemblerAgent").run(scenes, illustrations)
    artifact = {}
    BookAssemblerAgent(name="BookAssemblerAgent").run(scenes, illustrations, artifact=artifact)
    book_filename = "PixieLabs Book.pdf"
    session["book_filename"] = book_filename
    return {
        "book": f"/api/download-book?session_id={session_id}",
        "book_filename": book_filename,
        "illustrations": illustrations,
        "scenes": scenes,
    }

@app.get("/api/download-book")
def download_book(session_id: str):
    temp_dir = tempfile.gettempdir()
    session = session_store.get(session_id)
    if not session:
        return {"error": "Session not found"}
    book_filename = session.get("book_filename", "book.pdf")
    pdf_path = os.path.join(temp_dir, book_filename)
    if not os.path.exists(pdf_path):
        return {"error": "File not found"}
    return FileResponse(pdf_path, filename=book_filename, media_type="application/pdf") 