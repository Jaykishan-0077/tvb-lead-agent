"""
Central configuration for the TVB Lead Discovery Agent.

Target Architecture & Profile (from TVB's brief):
- Revenue or funding strictly between $1M and $5M USD.
- Tech-enabled platform.
- Minimal-to-no US presence.
- Named primary CEO/Co-founder.
- Exact corporate email with reliable primary or Hunter evidence (NO INFERRED/FABRICATED EMAILS).
- Six-Gate Hard Verification + Adversarial Break Testing.
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
    "requires_named_contact": True,  # Primary CEO or Co-founder
    "requires_verified_email": True,
}

# Machine-Readable Hard Rejection Codes
REJECTION_REASONS = {
    "TOTAL_FUNDING_ABOVE_LIMIT": "Current total funding exceeds $5M USD ceiling.",
    "FUNDING_ABOVE_LIMIT": "Total funding or revenue exceeds $5M USD cap.",
    "FUNDING_BELOW_LIMIT": "Total funding or revenue is below the minimum $1M USD threshold.",
    "REVENUE_NOT_VERIFIED": "No verified primary or secondary financial evidence found.",
    "OUTDATED_FINANCIAL_DATA": "Financial figures are outdated or reference stale predecessor rounds without total funding verification.",
    "US_PRESENCE_TOO_HIGH": "Entity has US headquarters, US operating entity, or significant US presence.",
    "US_PRESENCE_UNKNOWN": "US operational presence could not be verified from independent evidence.",
    "CEO_NOT_VERIFIED": "Primary CEO or Co-founder name could not be verified in leadership listings.",
    "CEO_ROLE_OUTDATED": "Executive listed is a former executive, secondary VP, or unverified advisor.",
    "EMAIL_NOT_VERIFIED": "No exact published primary email or high-confidence Hunter.io verification found.",
    "EMAIL_NOT_ASSOCIATED_WITH_CONTACT": "Discovered email does not belong to the named primary executive.",
    "COMPANY_INACTIVE": "Domain is parked, inaccessible, company is defunct or acquired.",
    "COMPANY_ACQUIRED_OR_CLOSED": "Company has been acquired or has ceased active independent operations.",
    "TECH_PLATFORM_NOT_VERIFIED": "Company does not operate a proprietary tech platform or SaaS product.",
    "CONFLICTING_SOURCES": "Conflicting data points between primary site and secondary registries.",
    "INSUFFICIENT_EVIDENCE": "Record lacks sufficient multi-source corroboration.",
    "ADVERSARIAL_FAILURE": "Adversarial audit identified disqualifying round >$5M, acquisition, or US entity.",
}

# Full Audit Trail Schema Columns for TVB Export
AUDIT_EXPORT_COLUMNS = [
    "company_name",
    "description",
    "industry_sector",
    "hq_country",
    "hq_source",
    "financial_type",
    "financial_amount_usd",
    "financial_date",
    "current_total_funding_usd",
    "current_revenue_usd",
    "financial_source_1",
    "financial_source_2",
    "financial_evidence",
    "technology_verified",
    "technology_source",
    "us_presence_status",
    "us_presence_source_1",
    "us_presence_source_2",
    "contact_name",
    "contact_title",
    "contact_source_1",
    "contact_source_2",
    "email",
    "email_verification_status",
    "email_source",
    "email_person_attributed",
    "email_evidence",
    "company_active",
    "active_source",
    "conflict_detected",
    "adversarial_result",
    "qualification_status",
    "rejection_reason",
    "confidence_score",
    "checked_at",
]

# Sectors pulled from TVB's Orbits
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

# Non-US geographies to bias discovery
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
    "recently raised seed funding",
    "raised $1 million 2025 2026",
    "raised $2 million seed round",
    "raised $3 million pre-series A",
    "raised $4 million 2025",
    "announced $2.5 million seed round",
    "secured $3 million funding 2025 2026",
    "current ARR $2 million platform",
    "annual recurring revenue $3 million",
    "closed $4 million seed funding",
]

# ---------------------------------------------------------------------------
# Run limits
# ---------------------------------------------------------------------------
MIN_QUALIFYING_LEADS = 15
MAX_DOMAINS_TO_SCAN = int(os.environ.get("TVB_MAX_DOMAINS", "100"))
MAX_SEARCH_QUERIES = int(os.environ.get("TVB_MAX_QUERIES", "50"))
RESULTS_PER_QUERY = int(os.environ.get("TVB_RESULTS_PER_QUERY", "6"))
REQUEST_TIMEOUT_SECS = 12
PAGE_TEXT_CHAR_LIMIT = 7000

# ---------------------------------------------------------------------------
# API keys / model config
# ---------------------------------------------------------------------------
ANTHROPIC_MODEL = os.environ.get("TVB_ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")
GEMINI_MODEL = os.environ.get("TVB_GEMINI_MODEL", "gemini-3.5-flash-lite")
OPENAI_MODEL = os.environ.get("TVB_OPENAI_MODEL", "gpt-4o-mini")


def _load_env_fallback():
    # Auto-load .env file if present
    env_paths = [
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.getcwd(), ".streamlit", "secrets.toml"),
    ]
    for ep in env_paths:
        if os.path.exists(ep):
            try:
                with open(ep, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip().strip('"').strip("'")
                            v = v.strip().strip('"').strip("'")
                            if k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass


_load_env_fallback()


def get_anthropic_api_key() -> str:
    _load_env_fallback()
    return os.environ.get("ANTHROPIC_API_KEY", "")


def get_gemini_api_key() -> str:
    _load_env_fallback()
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")


def get_tavily_api_key() -> str:
    _load_env_fallback()
    return os.environ.get("TAVILY_API_KEY", "")


def get_serpapi_api_key() -> str:
    _load_env_fallback()
    return os.environ.get("SERPAPI_API_KEY") or os.environ.get("SERPER_API_KEY", "")


def get_hunter_api_key() -> str:
    _load_env_fallback()
    return os.environ.get("HUNTER_API_KEY", "")


def get_openai_api_key() -> str:
    _load_env_fallback()
    return os.environ.get("OPENAI_API_KEY", "")


def get_active_provider() -> str:
    if get_gemini_api_key():
        return "gemini"
    if get_anthropic_api_key():
        return "anthropic"
    if get_openai_api_key():
        return "openai"
    return "gemini"
