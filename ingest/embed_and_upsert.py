"""Chunk, embed, and upsert every scraped record into Pinecone.

Reads data/all_records.json (built by ingest/merge.py), splits each record's
text into smaller chunks (long PDF/page text doesn't embed well as one big
blob), embeds each chunk with OpenAI, and upserts the vectors into the
Pinecone index. Chunk ids are deterministic (derived from the record's id),
so re-running this after a re-scrape updates existing vectors instead of
creating duplicates.

Usage (from project root, with venv active):
    python ingest\\embed_and_upsert.py
"""

import hashlib
import json
import sys
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from pinecone import Pinecone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from config.settings import (  # noqa: E402
    EMBED_MODEL,
    OPENAI_API_KEY,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
)

INPUT_FILE = PROJECT_ROOT / "data" / "all_records.json"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# How many chunks to send to OpenAI / Pinecone per API call.
EMBED_BATCH_SIZE = 100
UPSERT_BATCH_SIZE = 100

splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def make_id(record):
    """Generate deterministic ID from record content if not provided."""
    if "id" in record and record["id"]:
        return record["id"]
    # Same source+doc_type+url+text -> same id (matches merge.py behavior)
    basis = f"{record['source']}|{record['doc_type']}|{record['url']}|{record['text']}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def build_chunks(records):
    """Split every record's text into chunks, each with its own stable id."""
    chunks = []
    for record in records:
        record_id = make_id(record)
        pieces = splitter.split_text(record["text"])
        for i, piece in enumerate(pieces):
            chunks.append(
                {
                    "id": f"{record_id}-{i}",
                    "text": piece,
                    "metadata": {
                        "source": record["source"],
                        "doc_type": record["doc_type"],
                        "title": record["title"],
                        "url": record["url"],
                        "scraped_at": record["scraped_at"],
                        "text": piece,  # kept in metadata so query results include it
                    },
                }
            )
    return chunks


def batched(items, size):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def main():
    records = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    print(f"loaded {len(records)} records from {INPUT_FILE.name}")

    chunks = build_chunks(records)
    print(
        f"split into {len(chunks)} chunks (chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})"
    )

    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_INDEX_NAME)

    upserted = 0
    for batch in batched(chunks, EMBED_BATCH_SIZE):
        texts = [chunk["text"] for chunk in batch]
        response = openai_client.embeddings.create(model=EMBED_MODEL, input=texts)

        vectors = [
            {
                "id": chunk["id"],
                "values": embedding.embedding,
                "metadata": chunk["metadata"],
            }
            for chunk, embedding in zip(batch, response.data)
        ]

        for upsert_batch in batched(vectors, UPSERT_BATCH_SIZE):
            index.upsert(vectors=upsert_batch)

        upserted += len(vectors)
        print(f"  upserted {upserted}/{len(chunks)}")

    stats = index.describe_index_stats()
    print(f"\ndone. index total vector count: {stats.total_vector_count}")


if __name__ == "__main__":
    main()
