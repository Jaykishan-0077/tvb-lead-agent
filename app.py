import os
import pandas as pd
import streamlit as st

from lead_agent import config, pipeline

st.set_page_config(
    page_title="TVB Lead Discovery & 6-Gate Verification Agent",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# API key handling: Streamlit secrets first, then environment variables
# ---------------------------------------------------------------------------
def _load_secret(name: str) -> str:
    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""


for key_name in [
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "SERPER_API_KEY",
    "SERPAPI_API_KEY",
    "HUNTER_API_KEY",
]:
    if key_name not in os.environ:
        secret_val = _load_secret(key_name)
        if secret_val:
            os.environ[key_name] = secret_val

st.title("🧭 TVB Lead Discovery & Verification Agent")
st.caption(
    "An autonomous discovery and deterministic verification agent engineered for **The Venture Build (TVB)**. "
    "Implements a **Two-Pass Discovery Engine**, **6 Independent Hard Gates**, and an **Adversarial Red-Team Verifier**."
)

with st.sidebar:
    st.header("⚙️ Configuration")

    provider = st.selectbox(
        "AI Provider for Extraction",
        options=["Google Gemini (Recommended / Fast)", "Anthropic Claude", "OpenAI"],
        index=0 if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") else (1 if os.environ.get("ANTHROPIC_API_KEY") else 0),
    )

    if "Gemini" in provider:
        gemini_default = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or getattr(config, "get_gemini_api_key", lambda: "")()
        gemini_key_input = st.text_input(
            "Gemini API Key",
            value=gemini_default,
            type="password",
            help="Google Gemini AI Key",
        )
        if gemini_key_input:
            os.environ["GEMINI_API_KEY"] = gemini_key_input
            os.environ["GOOGLE_API_KEY"] = gemini_key_input
    elif "Anthropic" in provider:
        anthropic_default = os.environ.get("ANTHROPIC_API_KEY") or getattr(config, "get_anthropic_api_key", lambda: "")()
        anthropic_key_input = st.text_input(
            "Anthropic API Key",
            value=anthropic_default,
            type="password",
            help="Available from https://console.anthropic.com/",
        )
        if anthropic_key_input:
            os.environ["ANTHROPIC_API_KEY"] = anthropic_key_input
    else:
        openai_default = os.environ.get("OPENAI_API_KEY") or getattr(config, "get_openai_api_key", lambda: "")()
        openai_key_input = st.text_input(
            "OpenAI API Key",
            value=openai_default,
            type="password",
            help="Available from https://platform.openai.com/",
        )
        if openai_key_input:
            os.environ["OPENAI_API_KEY"] = openai_key_input

    st.markdown("---")
    st.subheader("🔍 Search Provider")
    serpapi_default = os.environ.get("SERPAPI_API_KEY") or os.environ.get("SERPER_API_KEY") or getattr(config, "get_serpapi_api_key", lambda: "")()
    serper_key_input = st.text_input(
        "SerpApi Key",
        value=serpapi_default,
        type="password",
        help="Google-backed search for fresh press releases and funding news.",
    )
    if serper_key_input:
        os.environ["SERPER_API_KEY"] = serper_key_input
        os.environ["SERPAPI_API_KEY"] = serper_key_input

    st.markdown("---")
    st.subheader("📧 Email Verification")
    hunter_default = os.environ.get("HUNTER_API_KEY") or getattr(config, "get_hunter_api_key", lambda: "")()
    hunter_key_input = st.text_input(
        "Hunter.io API Key",
        value=hunter_default,
        type="password",
        help="Live B2B email intelligence verification for primary executives.",
    )
    if hunter_key_input:
        os.environ["HUNTER_API_KEY"] = hunter_key_input

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

    run_clicked = st.button("🚀 Run Autonomous Lead Agent", type="primary", use_container_width=True)

if "qualified_leads" not in st.session_state:
    st.session_state.qualified_leads = []
if "rejected_leads" not in st.session_state:
    st.session_state.rejected_leads = []
if "funnel" not in st.session_state:
    st.session_state.funnel = {
        "discovered": 0,
        "fin_pass": 0,
        "tech_pass": 0,
        "us_pass": 0,
        "ceo_pass": 0,
        "email_pass": 0,
        "adversarial_pass": 0,
        "qualified": 0,
    }

if run_clicked:
    active_prov = config.get_active_provider()
    if not active_prov:
        st.error("⚠️ Please enter an API key in the sidebar to start discovery.")
    else:
        st.session_state.qualified_leads = []
        st.session_state.rejected_leads = []
        progress_bar = st.progress(0, text="Initializing Two-Pass Discovery & Verification Engine...")

        # Funnel Metrics Bar
        col1, col2, col3, col4, col5 = st.columns(5)
        m_disc = col1.metric("Candidates Scanned", 0)
        m_fin = col2.metric("Financial Gate ($1M-$5M)", 0)
        m_ceo = col3.metric("CEO Verified", 0)
        m_email = col4.metric("Exact Email Verified", 0)
        m_qual = col5.metric("FINAL QUALIFIED", 0)

        log_expander = st.expander("📋 Live Agent Execution & Audit Log", expanded=True)
        log_placeholder = log_expander.empty()
        log_lines = []

        for event in pipeline.run(
            min_leads=int(min_leads),
            max_domains=int(max_domains),
        ):
            etype = event["type"]
            if etype == "log":
                log_lines.append(event["message"])
                log_placeholder.code("\n".join(log_lines[-300:]), language=None)
            elif etype == "progress":
                scanned_count = event["scanned"]
                total_target = max(1, event["total"])
                pct = min(1.0, scanned_count / total_target)
                progress_bar.progress(pct, text=f"Scouting & 6-Gate Evaluating ({scanned_count}/{total_target})...")
            elif etype == "funnel":
                f = event["funnel"]
                st.session_state.funnel = f
                m_disc.metric("Candidates Scanned", f["discovered"])
                m_fin.metric("Financial Gate ($1M-$5M)", f["fin_pass"])
                m_ceo.metric("CEO Verified", f["ceo_pass"])
                m_email.metric("Exact Email Verified", f["email_pass"])
                m_qual.metric("FINAL QUALIFIED", f["qualified"])
            elif etype == "lead":
                st.session_state.qualified_leads.append(event["record"])
            elif etype == "done":
                st.session_state.qualified_leads = event.get("leads", [])
                st.session_state.rejected_leads = event.get("rejected_leads", [])
                progress_bar.progress(1.0, text="Discovery & Verification Completed!")

        st.success(f"🎉 Verification Complete — Found {len(st.session_state.qualified_leads)} proven leads meeting 100% of TVB rules!")

# ---------------------------------------------------------------------------
# Results Display & Export
# ---------------------------------------------------------------------------
tab_qual, tab_rej, tab_arch = st.tabs([
    f"🏆 Proven Qualified Leads ({len(st.session_state.qualified_leads)})",
    f"❌ Rejected Candidates Audit ({len(st.session_state.rejected_leads)})",
    "🛡️ 6-Gate Architecture & Rules",
])

with tab_qual:
    if st.session_state.qualified_leads:
        df_qual = pd.DataFrame(st.session_state.qualified_leads)
        st.dataframe(df_qual, use_container_width=True)
        st.download_button(
            "⬇️ Download qualified_leads.csv (100% Verified)",
            data=df_qual.to_csv(index=False).encode("utf-8"),
            file_name="qualified_leads.csv",
            mime="text/csv",
            type="primary",
        )
    else:
        st.info("No qualified leads generated yet. Run the agent using the sidebar.")

with tab_rej:
    if st.session_state.rejected_leads:
        df_rej = pd.DataFrame(st.session_state.rejected_leads)
        st.dataframe(df_rej, use_container_width=True)
        st.download_button(
            "⬇️ Download rejected_leads.csv (Audit Log)",
            data=df_rej.to_csv(index=False).encode("utf-8"),
            file_name="rejected_leads.csv",
            mime="text/csv",
        )
    else:
        st.caption("No rejected candidate records logged.")

with tab_arch:
    st.markdown(
        """
### 🛡️ TVB Deterministic 6-Gate Verification Rules
1. **Gate 1: Company Existence** — Verified root corporate domain with live DNS and active service.
2. **Gate 2: Financial Requirement** — Strictly between **$1M and $5M USD** current revenue or total funding raised. Outdated or late-stage rounds (> $5M) are deterministically rejected.
3. **Gate 3: Technology Platform** — Primary source clearly describes a proprietary tech/SaaS software platform.
4. **Gate 4: Minimal US Presence** — Verified non-US headquarters (Europe, UK, India, UAE, Singapore, etc.). Rejects Delaware shells and US operating entities.
5. **Gate 5: Primary Leadership** — Current primary Founder / CEO verified on official leadership pages.
6. **Gate 6: Exact Email Verification** — **STRICT NO-INFERENCE POLICY**: Never generates or hallucinates emails. Accepts only exact published corporate emails or high-confidence Hunter.io API verification ($\ge 70$).
7. **Adversarial Red-Team Audit** — Dedicated adversarial verification pass designed to catch late-stage funding, executive departures, or US flips.
        """
    )
