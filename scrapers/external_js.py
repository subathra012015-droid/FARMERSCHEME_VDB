"""Scrape external, JavaScript-rendered pages (config.sources.JS_SOURCES).

Sites like MyScheme and PMFBY build their content with JavaScript after the
page loads, so plain requests (fetch_html) only sees an empty shell. This
script uses a real headless browser (Playwright) to render the page first,
then parses the resulting HTML - same parsing ideas as structured.py /
semistructured.py, just a different way of fetching the HTML.

Usage (from project root, with venv active):
    python scrapers\\external_js.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from config.sources import HEADERS, JS_SOURCES, TIMEOUT  # noqa: E402
from scrapers.common import fetch_html_js, find_card_groups, strip_noise  # noqa: E402

OUTPUT_FILE = PROJECT_ROOT / "data" / "external_js.json"

# Below this length, text is almost always a nav link or button label, not content.
MIN_TEXT_LENGTH = 40

# Headings become the "title" for whatever plain text follows them.
TEXT_TAGS = ["h1", "h2", "h3", "h4", "p", "li"]

# TN's schemes page (JS_SOURCES["TN"]) only shows a search filter form - the
# real scheme list loads from this JSON API after picking a department in the
# dropdown (found via browser DevTools Network tab). Calling it directly is
# faster and more reliable than driving the dropdown with Playwright.
TN_API_URL = "https://www.tnagrisnet.tn.gov.in/Scheme_master/getSchemes/{dept_code}"
TN_DEPARTMENT_CODES = ["A", "H", "E", "SO", "M", "S", "T", "TU"]

# Concrete subsidy rates (e.g. "50% subsidy @ Rs.1250/ha") live one level
# deeper, under each scheme's input-type/component breakdown.
TN_INPUT_TYPE_URL = (
    "https://www.tnagrisnet.tn.gov.in/Scheme_master/loadInputType/{scheme_id}"
)
TN_INPUT_CLASS_URL = (
    "https://www.tnagrisnet.tn.gov.in/Scheme_master/getInputClass/{input_id}"
)


def scrape_source(name, url):
    """Render one JS page and pull out its text content.

    Tries repeated card/panel blocks first (how most scheme-listing SPAs lay
    out content); falls back to a plain heading/paragraph/list walk if no
    repeated blocks are found (e.g. a single content page, not a listing).
    """
    html = fetch_html_js(url)
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
                    "doc_type": "rendered",
                    "title": title,
                    "text": text,
                    "url": url,
                    "scraped_at": datetime.now().isoformat(timespec="seconds"),
                }
            )

    if records:
        print(f"  found {len(records)} card/panel blocks")
        return records

    # No repeated card layout found - fall back to a plain text walk.
    current_title = name
    for tag in soup.find_all(TEXT_TAGS):
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
                "doc_type": "rendered",
                "title": current_title,
                "text": text,
                "url": url,
                "scraped_at": datetime.now().isoformat(timespec="seconds"),
            }
        )

    print(
        f"  found {len(records)} records (fallback text walk - no card layout detected)"
    )
    return records


def fetch_subsidy_details(scheme_id):
    """Fetch subsidy rates for a scheme via its input-type/component cascade
    (the department-level scheme list has no subsidy amounts, only these
    deeper per-component endpoints do)."""
    details = []

    try:
        response = requests.post(
            TN_INPUT_TYPE_URL.format(scheme_id=scheme_id),
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        input_types = response.json()
    except requests.RequestException:
        return details

    for input_type in input_types:
        input_id = input_type.get("input_type_id")
        if not input_id:
            continue
        try:
            response = requests.post(
                TN_INPUT_CLASS_URL.format(input_id=input_id),
                headers=HEADERS,
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            classes = response.json()
        except requests.RequestException:
            continue

        for item in classes:
            pattern = (item.get("pattern_of_subsidy") or "").strip()
            if not pattern:
                continue
            class_name = (item.get("class_Name") or "").strip()
            details.append(f"{class_name}: {pattern}" if class_name else pattern)

    return details


def scrape_tn(url):
    """Call TN's scheme API directly for every department, instead of
    rendering the page and driving its dropdown filter."""
    records = []

    for dept_code in TN_DEPARTMENT_CODES:
        try:
            response = requests.post(
                TN_API_URL.format(dept_code=dept_code), headers=HEADERS, timeout=TIMEOUT
            )
            response.raise_for_status()
            schemes = response.json()
        except requests.RequestException as error:
            print(f"  failed dept {dept_code}: {error}")
            continue

        for scheme in schemes:
            desc = scheme.get("scheme_desc", "").strip()
            if not desc:
                continue  # entry has no real content (empty on the source itself)

            status = "Active" if scheme.get("active") == "yes" else "Expired/Inactive"
            text = f"{scheme['Scheme_Name']} (Status: {status})\n\n{desc}"
            eligibility = scheme.get("eligibility", "").strip()
            if eligibility:
                text += f"\n\nEligibility: {eligibility}"
            doc_req = scheme.get("doc_req", "").strip()
            if doc_req:
                text += f"\n\nDocuments required: {doc_req}"

            subsidy_details = fetch_subsidy_details(scheme["scheme_id"])
            if subsidy_details:
                text += "\n\nSubsidy details:\n" + "\n".join(subsidy_details)

            records.append(
                {
                    "source": "TN",
                    "doc_type": "api",
                    "title": scheme["Scheme_Name"],
                    "text": text,
                    "url": url,
                    "scraped_at": datetime.now().isoformat(timespec="seconds"),
                }
            )

    print(
        f"  found {len(records)} real schemes across {len(TN_DEPARTMENT_CODES)} departments"
    )
    return records


def main():
    all_records = []
    for name, url in JS_SOURCES.items():
        print(f"scraping {name}: {url}")
        if name == "TN":
            records = scrape_tn(url)
        else:
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
