"""Scrape semi-structured content: repeated card/panel/div layouts that
LOOK organized on screen but are not real HTML <table> elements.

Government scheme pages often list each scheme as its own <div class="card">
or similar repeated block, instead of table rows. This script is for that
shape of content, separate from structured.py (real tables/lists).

Usage (from project root, with venv active):
    python scrapers\\semistructured.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from config.sources import SOURCES  # noqa: E402
from scrapers.common import fetch_html, find_card_groups, strip_noise  # noqa: E402

OUTPUT_FILE = PROJECT_ROOT / "data" / "semistructured.json"

# Below this length, a card's text is almost always an icon/button, not content.
MIN_TEXT_LENGTH = 60


def scrape_source(name, url):
    """Fetch one page and pull out its repeated card/panel blocks."""
    html = fetch_html(url)
    if html is None:
        return []

    soup = strip_noise(BeautifulSoup(html, "lxml"))

    records = []
    seen_text = set()

    for group in find_card_groups(soup):
        for card in group:
            text = card.get_text(" ", strip=True)
            if len(text) < MIN_TEXT_LENGTH or text in seen_text:
                continue
            seen_text.add(text)

            heading = card.find(["h1", "h2", "h3", "h4"])
            title = heading.get_text(" ", strip=True) if heading else name

            records.append(
                {
                    "source": name,
                    "doc_type": "semistructured",
                    "title": title,
                    "text": text,
                    "url": url,
                    "scraped_at": datetime.now().isoformat(timespec="seconds"),
                }
            )

    print(f"  found {len(records)} card/panel blocks")
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
