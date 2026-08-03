"""Shared helpers for every scraper: fetching pages, downloading files, PDF text."""

from collections import defaultdict
from pathlib import Path

import requests
from pypdf import PdfReader

from config.sources import HEADERS, TIMEOUT

# These wrap menus/branding, never the actual scheme content - drop them first.
NOISE_TAGS = ["script", "style", "nav", "header", "footer", "noscript"]


def fetch_html(url):
    """GET a page and return its HTML text, or None if the request failed."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        return response.text
    except requests.RequestException as error:
        print(f"failed: {url} ({error})")
        return None


def fetch_html_js(url, wait_ms=3000):
    """Open a page in a real (headless) browser and return the rendered HTML.

    Use this only for pages listed in config.sources.JS_SOURCES - plain
    fetch_html() sees an empty shell for those, because their content is
    built by JavaScript after the page loads.
    """
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.goto(url, timeout=TIMEOUT * 1000)
            page.wait_for_timeout(wait_ms)  # let JS finish rendering
            html = page.content()
            browser.close()
            return html
    except Exception as error:  # Playwright raises its own error types
        print(f"failed (js): {url} ({error})")
        return None


def download_file(url, dest_path):
    """Download a binary file (PDF, xlsx, ...) to dest_path. Returns True on success."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(response.content)
        return True
    except requests.RequestException as error:
        print(f"failed to download: {url} ({error})")
        return False


def extract_pdf_text(pdf_path):
    """Return all text found in a PDF file, or '' if it can't be read (e.g. scanned image)."""
    try:
        reader = PdfReader(str(pdf_path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()
    except Exception as error:
        print(f"failed to read pdf: {pdf_path} ({error})")
        return ""


def strip_noise(soup):
    """Remove tags that only ever hold menus/branding, never real content."""
    for tag in soup.find_all(NOISE_TAGS):
        tag.decompose()
    return soup


def find_card_groups(soup, tags=("div", "section", "li", "article"), min_group_size=3):
    """Find repeated card/panel blocks (each scheme/news item in its own tag).

    Groups tags by (tag name, class list) - 3+ tags sharing the same class
    combination is a strong signal of a repeated layout, e.g. a list of
    scheme cards each rendered from the same template.
    """
    groups = defaultdict(list)
    for tag in soup.find_all(tags):
        classes = tag.get("class")
        if not classes:
            continue
        groups[(tag.name, tuple(sorted(classes)))].append(tag)

    card_groups = [
        members for members in groups.values() if len(members) >= min_group_size
    ]

    # Drop nested duplicates: if a card contains another card from the same
    # group (rare, but possible with wrapper/inner divs sharing a class),
    # keep only the outermost one so we don't record the same text twice.
    cleaned_groups = []
    for members in card_groups:
        members_set = set(id(tag) for tag in members)
        outer_only = [
            tag
            for tag in members
            if not any(id(parent) in members_set for parent in tag.parents)
        ]
        cleaned_groups.append(outer_only)
    return cleaned_groups
