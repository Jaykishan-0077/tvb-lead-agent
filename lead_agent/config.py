"""
Central configuration for the TVB Lead Discovery Agent.

Everything the agent needs to know about *what it is looking for* lives here,
so the rest of the pipeline stays generic and reusable.
"""

import os

# ---------------------------------------------------------------------------
# Target profile (from TVB's brief)
# ---------------------------------------------------------------------------
TARGET_PROFILE = {
    "revenue_or_funding_usd_min": 1_000_000,
    "revenue_or_funding_usd_max": 5_000_000,
    "requires_tech_platform": True,
    "requires_minimal_us_presence": True,
    "requires_named_contact": True,  # CEO or Co-founder name + email
}

# Sectors pulled from TVB's Orbits (healthcare, education, AI, cybersecurity,
# digital twin, fintech/payments, travel) plus general SaaS/B2B tech, since
# TVB also serves broader "technology-enabled" scale-ups.
SECTORS = [
    "healthcare technology",
    "digital health",
    "edtech",
    "workforce development technology",
    "applied AI",
    "AI agents platform",
    "AI infrastructure",
    "cybersecurity",
    "compliance and risk management software",
    "digital twin",
    "fintech",
    "embedded finance",
    "cross-border payments",
    "travel technology",
    "B2B SaaS platform",
    "B2B2C platform",
]

# Non-US geographies to bias discovery toward companies with "minimal to no
# US presence." This list is only used to *steer* search queries — the
# extraction/validation step is what actually decides US-presence, since a
# company headquartered in one of these regions could still have a large US
# office (and vice versa).
REGIONS = [
    "India",
    "United Kingdom",
    "Europe",
    "France",
    "Germany",
    "Southeast Asia",
    "Singapore",
    "Middle East",
    "UAE",
    "Africa",
    "Latin America",
    "Australia",
    "Canada",
]

FUNDING_SIGNAL_PHRASES = [
    "raised seed funding",
    "raised $1 million",
    "raised $2 million",
    "raised $3 million",
    "raised $4 million",
    "raised $5 million",
    "seed round",
    "pre-series A funding",
    "series A funding platform",
    "annual recurring revenue $2 million",
    "ARR $3 million platform",
]

# ---------------------------------------------------------------------------
# Run limits (kept conservative so a single click doesn't run forever or
# blow through free API tiers)
# ---------------------------------------------------------------------------
MIN_QUALIFYING_LEADS = 15
MAX_DOMAINS_TO_SCAN = int(os.environ.get("TVB_MAX_DOMAINS", "90"))
MAX_SEARCH_QUERIES = int(os.environ.get("TVB_MAX_QUERIES", "45"))
RESULTS_PER_QUERY = int(os.environ.get("TVB_RESULTS_PER_QUERY", "6"))
REQUEST_TIMEOUT_SECS = 12
PAGE_TEXT_CHAR_LIMIT = 6000

# US indicators used as a light heuristic before the LLM extraction step
US_TLDS = (".us", ".gov")
US_STATE_HINTS = [
    "california", "new york", "texas", "san francisco", "delaware",
    "united states", "usa", "u.s.", "america", "silicon valley",
]

# ---------------------------------------------------------------------------
# API keys / model config (read from environment or Streamlit secrets)
# ---------------------------------------------------------------------------
ANTHROPIC_MODEL = os.environ.get("TVB_ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")
GEMINI_MODEL = os.environ.get("TVB_GEMINI_MODEL", "gemini-3.5-flash-lite")
OPENAI_MODEL = os.environ.get("TVB_OPENAI_MODEL", "gpt-4o-mini")


def get_anthropic_api_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "")


def get_gemini_api_key() -> str:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")


def get_openai_api_key() -> str:
    return os.environ.get("OPENAI_API_KEY", "")


def get_active_provider() -> str:
    """Detects available LLM provider based on configured API keys."""
    if get_gemini_api_key():
        return "gemini"
    if get_anthropic_api_key():
        return "anthropic"
    if get_openai_api_key():
        return "openai"
    return ""
