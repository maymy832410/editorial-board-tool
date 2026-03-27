"""Configuration — all secrets from environment variables."""

import os

# ── OpenAlex API ──
OPENALEX_BASE_URL = "https://api.openalex.org"
OPENALEX_EMAIL = os.environ.get("OPENALEX_EMAIL", "maymy832410@gmail.com")

# ── ORCID API ──
ORCID_API_BASE_URL = "https://pub.orcid.org/v3.0"

# ── Crossref API ──
CROSSREF_BASE_URL = "https://api.crossref.org"

# ── Database ──
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ── Email credentials (JSON string from env) ──
EMAIL_CREDENTIALS_JSON = os.environ.get("EMAIL_CREDENTIALS", "")

# ── Defaults ──
DEFAULT_H_INDEX_MIN = 5
DEFAULT_H_INDEX_MAX = 100
DEFAULT_MAX_RESULTS = 2000
