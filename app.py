import os
import pandas as pd
import streamlit as st

from lead_agent import config, pipeline

st.set_page_config(
    page_title="TVB Lead Discovery Agent",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# API key handling: check Streamlit secrets first, then environment variables
# ---------------------------------------------------------------------------
def _load_secret(name: str) -> str:
    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""


for key_name in ["GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "SERPER_API_KEY"]:
    if key_name not in os.environ:
        secret_val = _load_secret(key_name)
        if secret_val:
            os.environ[key_name] = secret_val

st.title("🧭 TVB Lead Discovery Agent")
st.caption(
    "An autonomous agent designed for **The Venture Build (TVB)** to scout scale-ups "
    "matching TVB's target profile: **$1M–$5M revenue/funding**, **tech platform**, "
    "**minimal-to-no US presence**, with a **named CEO/Co-founder** and a **verified email**."
)

with st.sidebar:
    st.header("⚙️ Configuration")

    provider = st.selectbox(
        "AI Provider for Extraction",
        options=["Google Gemini (Recommended / Fast)", "Anthropic Claude", "OpenAI"],
        index=0 if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") else (1 if os.environ.get("ANTHROPIC_API_KEY") else 0),
    )

    if "Gemini" in provider:
        gemini_key_input = st.text_input(
            "Gemini API Key",
            value=os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", ""),
            type="password",
            help="Free key available from https://aistudio.google.com/",
        )
        if gemini_key_input:
            os.environ["GEMINI_API_KEY"] = gemini_key_input
            os.environ["GOOGLE_API_KEY"] = gemini_key_input
    elif "Anthropic" in provider:
        anthropic_key_input = st.text_input(
            "Anthropic API Key",
            value=os.environ.get("ANTHROPIC_API_KEY", ""),
            type="password",
            help="Available from https://console.anthropic.com/",
        )
        if anthropic_key_input:
            os.environ["ANTHROPIC_API_KEY"] = anthropic_key_input
    else:
        openai_key_input = st.text_input(
            "OpenAI API Key",
            value=os.environ.get("OPENAI_API_KEY", ""),
            type="password",
            help="Available from https://platform.openai.com/",
        )
        if openai_key_input:
            os.environ["OPENAI_API_KEY"] = openai_key_input

    st.markdown("---")
    st.subheader("🔍 Search Provider")
    serper_key_input = st.text_input(
        "Serper.dev API Key (Optional)",
        value=os.environ.get("SERPER_API_KEY", ""),
        type="password",
        help="Optional Google-backed search. If omitted, uses free DuckDuckGo search automatically.",
    )
    if serper_key_input:
        os.environ["SERPER_API_KEY"] = serper_key_input

    st.markdown("---")
    st.subheader("🎯 Search Parameters")
    min_leads = st.number_input(
        "Minimum qualifying leads target",
        min_value=5,
        max_value=100,
        value=config.MIN_QUALIFYING_LEADS,
        step=5,
    )
    max_domains = st.number_input(
        "Max company sites to scan",
        min_value=10,
        max_value=500,
        value=config.MAX_DOMAINS_TO_SCAN,
        step=10,
    )
    max_queries = st.number_input(
        "Max discovery queries",
        min_value=5,
        max_value=200,
        value=config.MAX_SEARCH_QUERIES,
        step=5,
    )

    run_clicked = st.button("🚀 Run Lead Discovery Agent", type="primary", use_container_width=True)

if "leads" not in st.session_state:
    st.session_state.leads = []

if run_clicked:
    active_prov = config.get_active_provider()
    if not active_prov:
        st.error(
            "⚠️ Please enter an API key in the sidebar (Gemini, Claude, or OpenAI) "
            "so the agent can analyze scraped pages and extract structured parameters."
        )
    else:
        st.session_state.leads = []
        progress_bar = st.progress(0, text="Initializing autonomous discovery...")
        col_m1, col_m2, col_m3 = st.columns(3)
        m_scanned = col_m1.metric("Domains Scanned", 0)
        m_leads = col_m2.metric("Qualifying Leads Found", 0)
        m_status = col_m3.metric("Discovery Status", "Active")

        log_expander = st.expander("📋 Live Agent Execution Log", expanded=True)
        log_lines = []
        results_placeholder = st.empty()

        for event in pipeline.run(
            min_leads=int(min_leads),
            max_domains=int(max_domains),
            max_queries=int(max_queries),
        ):
            etype = event["type"]
            if etype == "log":
                log_lines.append(event["message"])
                log_expander.code("\n".join(log_lines[-250:]), language=None)
            elif etype == "progress":
                scanned_count = event["scanned"]
                total_target = max(1, event["total"])
                pct = min(1.0, scanned_count / total_target)
                progress_bar.progress(
                    pct, text=f"Scanning & evaluating domains ({scanned_count}/{total_target})..."
                )
                col_m1.metric("Domains Scanned", scanned_count)
            elif etype == "lead":
                st.session_state.leads.append(event["record"])
                col_m2.metric("Qualifying Leads Found", len(st.session_state.leads))
                df = pd.DataFrame(st.session_state.leads)
                results_placeholder.dataframe(df, use_container_width=True)
            elif etype == "done":
                st.session_state.leads = event["leads"]
                progress_bar.progress(1.0, text="Discovery run completed!")
                col_m3.metric("Discovery Status", "Completed")

        st.success(f"🎉 Run complete — Found {len(st.session_state.leads)} fully qualified leads matching TVB's profile!")

if st.session_state.leads:
    st.subheader(f"📊 Qualifying Scale-Up Leads ({len(st.session_state.leads)})")
    df = pd.DataFrame(st.session_state.leads)
    st.dataframe(df, use_container_width=True)
    st.download_button(
        "⬇️ Download Leads as CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="tvb_qualifying_leads.csv",
        mime="text/csv",
    )
else:
    st.info("👈 Enter your API key in the sidebar and click **🚀 Run Lead Discovery Agent** to start.")

with st.expander("ℹ️ How the Agent Discovers & Validates Leads"):
    st.markdown(
        """
1. **Dynamic Multi-Vector Discovery** — Combines TVB's Orbit verticals (Healthcare, EdTech, Applied AI, Cybersecurity, Digital Twin, Fintech, Travel) with non-US hubs (India, UK, France/Europe, UAE/Middle East, SEA, LATAM, etc.) and funding phrases, plus LLM-brainstormed search queries.
2. **Autonomous Web Scraping** — Visits discovered candidate websites and explores relevant subpages (`/about`, `/team`, `/leadership`, `/contact`, `/company`).
3. **Structured Entity Extraction** — Uses LLMs with strict zero-hallucination rules to parse revenue/funding figures, tech platform status, headquarters/geography, and named leadership.
4. **Multi-Constraint Profile Validation**:
   - **$1M–$5M USD** revenue or funding raised
   - **Tech-enabled platform**
   - **Minimal-to-no US presence**
   - **Named CEO/Co-founder** with **verified email** (validated via live DNS MX checks)
        """
    )

