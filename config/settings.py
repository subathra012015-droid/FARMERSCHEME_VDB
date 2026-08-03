"""Pinecone + OpenAI settings shared by ingest and backend code."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_settings():
    load_dotenv(PROJECT_ROOT / ".env", override=True)

    global OPENAI_API_KEY
    global PINECONE_API_KEY
    global PINECONE_INDEX_NAME
    global EMBED_MODEL
    global EMBED_DIMENSION
    global CHAT_MODEL

    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
    PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "").strip()
    PINECONE_INDEX_NAME = os.environ.get(
        "PINECONE_INDEX_NAME", "farmerscheme-db"
    ).strip()
    EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
    EMBED_DIMENSION = (
        1536  # must match EMBED_MODEL - text-embedding-3-small outputs 1536 dims
    )
    CHAT_MODEL = os.environ.get("CHAT_MODEL", "gpt-4o-mini")


load_settings()
