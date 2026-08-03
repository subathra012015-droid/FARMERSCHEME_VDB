"""Merge every scraper's JSON output into one unified, deduplicated list.

Reads data/structured.json, data/semistructured.json, data/unstructured_pdfs.json
and data/external_js.json (skipping any that don't exist yet), drops exact
duplicate text, and gives every record a stable id - so re-running this after
re-scraping updates existing Pinecone vectors instead of creating duplicates
(Phase 5 will use this id as the Pinecone vector id).

Usage (from project root, with venv active):
    python ingest\\merge.py
"""

import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_FILE = DATA_DIR / "all_records.json"

INPUT_FILES = [
    DATA_DIR / "structured.json",
    DATA_DIR / "semistructured.json",
    DATA_DIR / "unstructured_pdfs.json",
    DATA_DIR / "external_js.json",
]


def load_records(path):
    if not path.exists():
        print(f"  skipping (not found yet): {path.name}")
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def make_id(record):
    """Same source+doc_type+url+text -> same id, so a re-scrape of unchanged
    content updates the same Pinecone vector instead of adding a duplicate."""
    basis = f"{record['source']}|{record['doc_type']}|{record['url']}|{record['text']}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def main():
    merged = []
    seen_text = set()
    duplicates_dropped = 0

    for path in INPUT_FILES:
        records = load_records(path)
        kept = 0

        for record in records:
            text = record.get("text", "").strip()
            if not text:
                continue

            key = (record["source"], text)
            if key in seen_text:
                duplicates_dropped += 1
                continue
            seen_text.add(key)

            record["id"] = make_id(record)
            merged.append(record)
            kept += 1

        print(f"  {path.name}: {kept}/{len(records)} kept")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\ndropped {duplicates_dropped} exact duplicates")
    print(f"saved {len(merged)} unified records -> {OUTPUT_FILE}")

    print("\nby doc_type:")
    by_type = {}
    for record in merged:
        by_type[record["doc_type"]] = by_type.get(record["doc_type"], 0) + 1
    for doc_type, count in sorted(by_type.items()):
        print(f"  {doc_type:15} {count}")

    print("\nby source:")
    by_source = {}
    for record in merged:
        by_source[record["source"]] = by_source.get(record["source"], 0) + 1
    for source, count in sorted(by_source.items()):
        print(f"  {source:20} {count}")


if __name__ == "__main__":
    main()
