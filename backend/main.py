"""FastAPI backend: one /chat endpoint tying Pinecone retrieval + OpenAI chat
+ SQLite history together.

Usage (from project root, with venv active):
    uvicorn backend.main:app --reload
"""

import sys
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from backend import memory, rag  # noqa: E402
from backend.models import ChatRequest, ChatResponse, SourceOut  # noqa: E402

app = FastAPI(title="FarmerScheme DB Chatbot")

# Local-only dev setup: Streamlit frontend runs on a different port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://0.0.0.0:8501",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    memory.init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())

    history = memory.get_recent_messages(session_id)
    memory.save_message(session_id, "user", request.message)

    try:
        answer, sources = rag.generate_answer(
            request.message, history=history, language=request.language
        )
    except Exception as exc:
        answer = f"The chatbot could not complete the request: {exc}"
        sources = []

    memory.save_message(session_id, "assistant", answer)

    return ChatResponse(
        session_id=session_id,
        answer=answer,
        sources=[SourceOut(**source) for source in sources],
    )
