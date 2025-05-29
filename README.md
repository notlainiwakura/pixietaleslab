# PixieTales Lab

PixieTales Lab is a multi-agent, full-stack application for generating personalized children's coloring books using Google Cloud's Agent Development Kit (ADK). The system orchestrates several specialized agents to turn simple user input into a complete, downloadable PDF coloring book with AI-generated stories and illustrations.

---

## Project Summary
PixieTales Lab demonstrates the power of multi-agent orchestration using ADK. Users provide a few story ingredients (character, animal, setting, and an optional "special sauce"), and the system generates a gentle, imaginative children's story, splits it into scenes, creates illustration prompts, generates doodle-style images, and assembles everything into a PDF book—all through coordinated agent interactions.

---

## Features & Functionality
- **Multi-Agent Orchestration:** Each step (input validation, story generation, element extraction, prompt crafting, illustration, PDF assembly) is handled by a dedicated agent, coordinated by an ADK workflow.
- **AI Story Generation:** Uses Google Vertex AI (Gemini) to create safe, moral children's stories.
- **Scene Splitting & Prompting:** Breaks stories into scenes and generates illustration prompts.
- **AI Illustration Generation:** Uses Vertex AI Imagen for black-and-white, coloring-book-style images.
- **PDF Book Assembly:** Combines story and images into a downloadable PDF.
- **Modern Frontend:** React + Material-UI, mobile-friendly, with a pastel theme.

---

## Technologies Used
- **Google Agent Development Kit (ADK):** For agent design and orchestration (Python)
- **Google Vertex AI (Gemini, Imagen):** For story and image generation
- **FastAPI:** Backend API
- **ReportLab:** PDF generation
- **React + Material-UI:** Frontend
- **Python 3.9+**, **TypeScript**, **Node.js**
- **Firebase Hosting:** For production frontend deployment
- **Docker:** For containerized backend deployment

---

## Architecture & Orchestration
- **Agents:**
  - `UserInputAgent`: Validates/randomizes user input
  - `StoryGeneratorAgent`: Generates the story
  - `StoryElementsAgent`: Extracts main character/setting
  - `CoherenceAgent`: Splits story, crafts illustration prompts
  - `IllustrationGeneratorAgent`: Generates images
  - `BookAssemblerAgent`: Assembles the PDF
- **Workflow:**
  - Orchestrated via ADK's `SequentialAgent` and `ParallelAgent` primitives in `book_generator.py`
  - Each agent is responsible for a single, well-defined task
  - The workflow is visible and central to the project design

---

## Updated Book Generation Flow (Async)

- When you request a book, the backend now starts the book generation as a **background job** and immediately returns a `session_id` and a `pending` status.
- The frontend (or API client) should **poll** the endpoint `/api/book-status?session_id=...` to check the status of the book generation.
- When the status is `done`, the response will include the download link and illustration URLs. If there is an error, the status will be `error` and an error message will be provided.
- This async pattern avoids HTTP timeouts and makes the app more reliable for long-running jobs (such as generating multiple images and assembling the PDF).

---

## Deployment

### 1. Backend (FastAPI) with Docker

1. **Build the Docker image:**
   ```bash
   cd new
   docker buildx build --platform linux/amd64 -t gcr.io/bookmaker-459918/pixietales-backend:v1 .
   ```
2. **Push the image to Google Container Registry:**
   ```bash
   docker push gcr.io/bookmaker-459918/pixietales-backend:v1
   ```
3. **Deploy to Cloud Run:**
   ```bash
   gcloud run deploy pixietales-backend-997768032370 \
     --image gcr.io/bookmaker-459918/pixietales-backend:v1 \
     --region us-central1 \
     --update-env-vars=GOOGLE_CLOUD_PROJECT=bookmaker-459918,GCS_BUCKET_NAME=pixietales-books \
     --timeout=300
   ```

### 2. Frontend (React) with Firebase Hosting

1. **Install dependencies and build the frontend:**
   ```bash
   cd new/frontend
   npm install
   npm run build
   ```
2. **Set the API base URL:**
   - In your React app, set the environment variable `REACT_APP_API_BASE_URL` to point to your backend (e.g., `https://your-backend-domain.com`).
   - You can do this by creating a `.env.production` file in `new/frontend`:
     ```env
     REACT_APP_API_BASE_URL=https://your-backend-domain.com
     ```
3. **Deploy to Firebase Hosting:**
   ```bash
   firebase deploy --only hosting
   ```
   - After deployment, Firebase will provide a live URL for your frontend.

---

## Usage
1. Visit your deployed frontend (Firebase Hosting URL).
2. Choose "Surprise me!" or "Create my own" to generate a story.
3. The UI will show progress while your book is being generated. When ready, you can download your personalized coloring book PDF.

---

## Notes
- **Book generation is now async:** The backend starts a background job and the frontend polls for status. This avoids timeouts and improves reliability for long jobs.
- **Environment Variables:** Ensure all required Google Cloud and API credentials are set in your backend `.env` file.
- **Connecting Frontend and Backend:** The frontend must be configured to use the correct API base URL for production.

---

## Findings & Learnings
- **Agent orchestration** with ADK enables clear, maintainable, and extensible workflows.
- **Separation of concerns**: Each agent is focused, making the system easy to debug and extend.
- **Google Cloud integration**: Vertex AI provides high-quality generative models for both text and images.
- **Frontend/Backend separation**: Enables rapid iteration and clear API boundaries.
- **Challenges**: Managing async agent orchestration, handling API rate limits, and ensuring a smooth user experience.

---

## License
This project is for educational/demo use. See individual package licenses for details.

# PixieTales Lab Backend

## Overview
This backend generates personalized children's coloring books using AI. It now uses **Google Firestore** for persistent session storage and **Google Cloud Storage (GCS)** for persistent PDF and illustration file storage, making it production-ready and scalable on Google Cloud Run.

---

## Features
- FastAPI backend
- Persistent session storage with Firestore
- Persistent PDF and illustration storage with GCS
- Cloud Run ready (stateless, scalable)
- Google Vertex AI, ReportLab, and Google ADK integration

---

## Setup

### 1. Prerequisites
- Python 3.9+
- Google Cloud project
- Firestore database (Native mode, Region: us-central1 recommended)
- GCS bucket (e.g., `pixietales-books`)
- Service account with required IAM roles (see below)

### 2. Install Dependencies
```sh
pip install -r requirements.txt
```

### 3. Environment Variables
Set the following environment variables (in Cloud Run or locally):
- `GCS_BUCKET_NAME` (your GCS bucket name)
- `GOOGLE_APPLICATION_CREDENTIALS` (path to your service account key, for local dev only)

### 4. IAM Roles
Your service account must have:
- **Cloud Datastore User** (`roles/datastore.user`)
- **Storage Object Admin** (`roles/storage.objectAdmin`)
- (Optional) **Logging Log Writer** (`roles/logging.logWriter`)

---

## Running Locally

1. Set up credentials:
   ```sh
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/bookmaker-service-account.json"
   ```
2. Start the server:
   ```sh
   uvicorn api_server:app --host 0.0.0.0 --port 8080
   ```
3. Or, using Docker:
   ```sh
   docker build -t pixietales-backend .
   docker run -p 8080:8080 \
     -e GOOGLE_APPLICATION_CREDENTIALS=/app/bookmaker-service-account.json \
     -v "/path/to/bookmaker-service-account.json:/app/bookmaker-service-account.json" \
     pixietales-backend
   ```

---

## Deploying to Cloud Run

1. Build and submit the Docker image:
   ```sh
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/pixietales-backend:TAG
   ```
2. Deploy to Cloud Run:
   ```sh
   gcloud run deploy pixietales-backend-997768032370 \
     --image gcr.io/YOUR_PROJECT_ID/pixietales-backend:TAG \
     --region us-central1 \
     --platform managed \
     --allow-unauthenticated
   ```
3. (Optional) Set environment variables:
   ```sh
   gcloud run services update pixietales-backend-997768032370 \
     --update-env-vars GCS_BUCKET_NAME=pixietales-books \
     --region us-central1
   ```

---

## Notes
- All session data is stored in Firestore for persistence across Cloud Run instances.
- All PDFs and illustrations are uploaded to GCS and served via public URLs.
- Local `/tmp` files are cleaned up after upload.
- For production, consider using signed URLs for private file access.

---

## Troubleshooting
- **Container fails to start:** Check that all dependencies are in `requirements.txt` and that your app listens on port 8080.
- **Auth errors:** Make sure your service account has the required IAM roles and credentials are set.
- **Session not found:** Ensure Firestore is set up and accessible from your service account.
- **Files not found:** Ensure GCS bucket exists and permissions are correct.

---

## License
MIT 