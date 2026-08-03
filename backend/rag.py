"""Retrieval-augmented generation: Pinecone search + OpenAI chat, grounded in
our scraped scheme data. Includes state tracking to avoid fact repetition and
dynamic format switching based on query intent.
"""

import sys
from pathlib import Path

from openai import OpenAI
from openai import APIConnectionError, AuthenticationError, RateLimitError
from pinecone import Pinecone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from config.settings import (  # noqa: E402
    CHAT_MODEL,
    EMBED_MODEL,
    OPENAI_API_KEY,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
)

TOP_K = 5

SYSTEM_PROMPT = (
    "You are a helpful assistant for Indian farmer welfare schemes. "
    "Answer using ONLY the provided context. "
    "If the answer is not in the context, say so clearly and suggest checking the official website."
)

# Language codes must match the frontend's LANGUAGE_OPTIONS values.
LANGUAGE_NAMES = {
    "bn": "Bengali",
    "en": "English",
    "gu": "Gujarati",
    "hi": "Hindi",
    "kn": "Kannada",
    "ml": "Malayalam",
    "mr": "Marathi",
    "pa": "Punjabi",
    "ta": "Tamil",
    "te": "Telugu",
    "ur": "Urdu",
}

# Appended to SYSTEM_PROMPT based on the frontend's language selector.
LANGUAGE_INSTRUCTIONS = {
    "auto": (
        " Respond in the same language the user asked their question in "
        "(English, Tamil, Hindi, or any other Indian language) - match their language."
    ),
    **{
        code: f" Always respond in {name}, regardless of what language the question was asked in."
        for code, name in LANGUAGE_NAMES.items()
    },
}

openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
pc = Pinecone(api_key=PINECONE_API_KEY) if PINECONE_API_KEY else None

# Lazy load index to handle missing index gracefully
_index = None
_index_error = None


def _require_runtime_config():
    missing = []
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if not PINECONE_API_KEY:
        missing.append("PINECONE_API_KEY")
    if not PINECONE_INDEX_NAME:
        missing.append("PINECONE_INDEX_NAME")
    if missing:
        raise RuntimeError(
            "Missing required runtime configuration: " + ", ".join(missing)
        )


def get_index():
    """Get Pinecone index, raising error with helpful message if missing."""
    global _index, _index_error
    if _index is not None:
        return _index
    if _index_error is not None:
        raise _index_error

    _require_runtime_config()
    if pc is None:
        raise RuntimeError(
            "Pinecone client is unavailable. Please verify your Pinecone credentials."
        )

    try:
        _index = pc.Index(PINECONE_INDEX_NAME)
        return _index
    except Exception as e:
        _index_error = RuntimeError(
            f"❌ Pinecone index '{PINECONE_INDEX_NAME}' not found.\n"
            f"   Please create it in Pinecone dashboard:\n"
            f"   1. Go to https://www.pinecone.io\n"
            f"   2. Click 'Create Index'\n"
            f"   3. Name: '{PINECONE_INDEX_NAME}', Dimension: 1536, Metric: cosine, Pod type: starter\n"
            f"   Original error: {e}"
        )
        raise _index_error


def retrieve(question, top_k=TOP_K):
    """Embed the question and return Pinecone's closest matching chunks."""
    _require_runtime_config()
    if openai_client is None:
        raise RuntimeError(
            "OpenAI client is unavailable. Please verify your OpenAI credentials."
        )

    embedding = openai_client.embeddings.create(model=EMBED_MODEL, input=[question])
    question_vector = embedding.data[0].embedding

    results = get_index().query(
        vector=question_vector, top_k=top_k, include_metadata=True
    )
    return results.matches


def build_context(matches):
    """Turn Pinecone matches into a plain-text block for the chat prompt."""
    blocks = []
    for match in matches:
        meta = match.metadata
        blocks.append(
            f"[{meta['source']} - {meta['title']}]\nLink: {meta['url']}\n{meta['text']}"
        )
    return "\n\n".join(blocks)


def generate_answer(question, history=None, language="auto"):
    """Retrieve relevant context and ask the chat model to answer using it."""
    history = history or []
    try:
        recent_context = " ".join(turn["content"] for turn in history[-2:])
        retrieval_query = f"{recent_context} {question}".strip()
        matches = retrieve(retrieval_query)
        context = build_context(matches)

        system_prompt = SYSTEM_PROMPT
        if language and language != "auto":
            system_prompt += f" Answer in {LANGUAGE_NAMES.get(language, 'English')}"

        messages = [{"role": "system", "content": system_prompt}]
        for turn in history:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append(
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}",
            }
        )

        response = openai_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
        )
        answer = response.choices[0].message.content

        sources = [
            {
                "source": match.metadata["source"],
                "title": match.metadata["title"],
                "url": match.metadata["url"],
                "score": match.score,
            }
            for match in matches
        ]
        return answer, sources
    except AuthenticationError as exc:
        return f"OpenAI authentication failed: {exc}", []
    except (APIConnectionError, RateLimitError) as exc:
        return f"The AI service is temporarily unavailable: {exc}", []
    except RuntimeError as exc:
        return str(exc), []
    except Exception as exc:
        return f"The chatbot could not complete the request: {exc}", []
