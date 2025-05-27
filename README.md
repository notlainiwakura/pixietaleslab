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

## Deployment

### 1. Backend (FastAPI) with Docker

1. **Build the Docker image:**
   ```bash
   cd new
   docker build -t pixietales-backend .
   ```
2. **Run the backend container:**
   ```bash
   docker run -d -p 8008:8008 --env-file .env pixietales-backend
   ```
   - The backend will be available at `http://<your-server-ip>:8008`
   - Ensure your `.env` file contains all required Google Cloud credentials and environment variables.

### 2. Frontend (React) with Firebase Hosting

1. **Install dependencies and build the frontend:**
   ```bash
   cd new/frontend
   npm install
   npm run build
   ```
2. **Set the API base URL:**
   - In your React app, set the environment variable `REACT_APP_API_BASE_URL` to point to your backend (e.g., `https://your-backend-domain.com` or your server IP).
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
3. Download your personalized coloring book PDF.

---

## Notes
- **No local development instructions are provided here.** This README is focused on production deployment. For local development, use standard React and FastAPI workflows as needed.
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