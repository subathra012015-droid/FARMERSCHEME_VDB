"""Combine every scraper's JSON output into one Excel workbook, for human review.

This is a read-only inspection tool - Pinecone (not this file) is still the
real database the chatbot queries. Re-run this any time after scraping to
refresh the workbook.

Usage (from project root, with venv active):
    python scrapers\\export_to_excel.py
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_FILE = DATA_DIR / "scraped_data_review.xlsx"

# sheet name -> JSON file produced by each scraper
CATEGORY_FILES = {
    "structured": DATA_DIR / "structured.json",
    "semistructured": DATA_DIR / "semistructured.json",
    "unstructured_pdfs": DATA_DIR / "unstructured_pdfs.json",
    "external_js": DATA_DIR / "external_js.json",
}

# Control characters Excel refuses to store (sometimes present in PDF text extracts).
ILLEGAL_CHARACTERS_RE = re.compile(r"[\000-\010]|[\013-\014]|[\016-\037]")

# Excel's hard limit per cell.
MAX_CELL_LENGTH = 32000


def clean_cell(value):
    if not isinstance(value, str):
        return value
    value = ILLEGAL_CHARACTERS_RE.sub("", value)
    return value[:MAX_CELL_LENGTH]


def load_records(path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    summary_rows = []
    sheets_written = 0

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        for category, path in CATEGORY_FILES.items():
            records = load_records(path)
            if not records:
                print(f"{category:20} 0 records (missing or empty: {path.name})")
                continue

            frame = pd.DataFrame(records)
            frame = frame.map(clean_cell)
            frame.to_excel(writer, sheet_name=category, index=False)
            sheets_written += 1
            print(f"{category:20} {len(frame)} records -> sheet '{category}'")

            for source, count in frame["source"].value_counts().items():
                summary_rows.append(
                    {"category": category, "source": source, "records": count}
                )

        if summary_rows:
            pd.DataFrame(summary_rows).to_excel(
                writer, sheet_name="summary", index=False
            )

    if sheets_written == 0:
        print("\nNo data found - run the scraper scripts first.")
        return

    print(f"\nsaved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
