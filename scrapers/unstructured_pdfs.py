"""Scrape unstructured content: PDF documents linked from each source page.

Government scheme rules are often published as PDFs, not web pages. This
script finds every PDF link on a source page, downloads the PDF, and pulls
out its text - separate from structured.py/semistructured.py, because PDFs
need a completely different extraction technique (pypdf, not BeautifulSoup).

Usage (from project root, with venv active):
    python scrapers\\unstructured_pdfs.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from config.sources import SOURCES  # noqa: E402
from scrapers.common import download_file, extract_pdf_text, fetch_html  # noqa: E402

OUTPUT_FILE = PROJECT_ROOT / "data" / "unstructured_pdfs.json"
PDF_DIR = PROJECT_ROOT / "data" / "pdf_files"

# A big govt page can link 100+ PDFs - cap it so a first run finishes quickly.
MAX_PDFS_PER_SOURCE = 15


def find_pdf_links(html, page_url):
    """Return absolute URLs of every <a href="...pdf"> link on the page."""
    soup = BeautifulSoup(html, "lxml")
    pdf_links = []

    for link in soup.find_all("a", href=True):
        href = link[
            "href"
        ].strip()  # some sites (e.g. dmi.gov.in) leave trailing spaces
        if href.lower().endswith(".pdf"):
            full_url = urljoin(page_url, href)
            if full_url not in pdf_links:
                pdf_links.append(full_url)

    return pdf_links


def scrape_source(name, url):
    """Find every PDF on this source's page, download it, extract its text."""
    html = fetch_html(url)
    if html is None:
        return []

    pdf_urls = find_pdf_links(html, url)[:MAX_PDFS_PER_SOURCE]
    print(f"  found {len(pdf_urls)} pdf links (capped at {MAX_PDFS_PER_SOURCE})")

    records = []
    for pdf_url in pdf_urls:
        file_name = pdf_url.split("/")[-1].split("?")[0] or "document.pdf"
        local_path = PDF_DIR / name / file_name

        if not download_file(pdf_url, local_path):
            continue

        text = extract_pdf_text(local_path)
        if not text:
            print(f"    skipped (no extractable text): {file_name}")
            continue

        records.append(
            {
                "source": name,
                "doc_type": "pdf",
                "title": file_name,
                "text": text,
                "url": pdf_url,
                "scraped_at": datetime.now().isoformat(timespec="seconds"),
            }
        )

    print(f"  kept {len(records)} pdfs with usable text")
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
