"""Single source of truth for every URL the scrapers visit.

Nickname -> URL. The nickname becomes the 'source' tag stored as metadata
on every vector in Pinecone, so answers can cite where they came from.
"""

SOURCES = {
    "Central_PMKisan": "https://pmkisan.gov.in/",
    "Central_AgriWelfare": "https://agriwelfare.gov.in/",
    "Central_DMI": "https://dmi.gov.in/",
}

# Pages that render their content with JavaScript - plain requests will see
# an empty shell (or raw template code like {{item.name}}) here. These need
# Playwright instead.
JS_SOURCES = {
    # Confirmed 03-Aug-2026: plain requests returns unrendered Angular
    # templates like {{lang=='en'?'Home':'...'}} instead of real text.
    "TN": "https://www.tnagrisnet.tn.gov.in/home/schemes/",
    "MyScheme": "https://www.myscheme.gov.in/",
    "PMFBY": "https://pmfby.gov.in/",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TIMEOUT = 30
