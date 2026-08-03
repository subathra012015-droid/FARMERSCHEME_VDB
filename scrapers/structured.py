"""Scrape real content (paragraphs, list items, headings) from a government page.

Usage (from project root, with venv active):
    python scrapers\\structured.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from config.sources import SOURCES  # noqa: E402
from scrapers.common import fetch_html  # noqa: E402

OUTPUT_FILE = PROJECT_ROOT / "data" / "structured.json"

# Below this length, text is almost always a nav link or button label, not content.
MIN_TEXT_LENGTH = 40

# These wrap menus/branding, never the actual scheme content - drop them first.
NOISE_TAGS = ["script", "style", "nav", "header", "footer", "noscript"]

# Walked top-to-bottom: headings become the "title" for whatever follows them.
CONTENT_TAGS = ["h1", "h2", "h3", "h4", "p", "li", "td"]


def scrape_source(name, url):
    """Fetch one page and pull out its real paragraph/list/table-cell text."""
    html = fetch_html(url)
    if html is None:
        return []

    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(NOISE_TAGS):
        tag.decompose()

    records = []
    seen_text = set()
    current_title = name

    for tag in soup.find_all(CONTENT_TAGS):
        text = tag.get_text(" ", strip=True)
        if not text:
            continue

        if tag.name in ("h1", "h2", "h3", "h4"):
            current_title = text
            continue

        if len(text) < MIN_TEXT_LENGTH or text in seen_text:
            continue
        seen_text.add(text)

        records.append(
            {
                "source": name,
                "doc_type": "structured",
                "title": current_title,
                "text": text,
                "url": url,
                "scraped_at": datetime.now().isoformat(timespec="seconds"),
            }
        )

    print(f"  kept {len(records)} content blocks (after dropping nav/short text)")
    return records


def main():
    all_records = []
    for name, url in SOURCES.items():
        print(f"scraping {name}: {url}")
        records = scrape_source(name, url)
        print(f"  -> {len(records)} records")
        all_records.extend(records)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(all_records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nsaved {len(all_records)} records -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
