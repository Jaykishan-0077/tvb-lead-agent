import os

import pandas as pd
import streamlit as st

from lead_agent import config, pipeline

st.set_page_config(page_title="TVB Lead Discovery Agent", page_icon="🧭", layout="wide")

# ---------------------------------------------------------------------------
# API key handling: prefer Streamlit secrets (for the hosted deployment),
# fall back to a sidebar input so anyone can trigger a run without editing
# any files.
# ---------------------------------------------------------------------------
def _load_key(name: str) -> str:
    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""


if "ANTHROPIC_API_KEY" not in os.environ:
    key_from_secrets = _load_key("ANTHROPIC_API_KEY")
    if key_from_secrets:
        os.environ["ANTHROPIC_API_KEY"] = key_from_secrets

if "SERPER_API_KEY" not in os.environ:
    serper_from_secrets = _load_key("SERPER_API_KEY")
    if serper_from_secrets:
        os.environ["SERPER_API_KEY"] = serper_from_secrets

st.title("🧭 TVB Lead Discovery Agent")
st.caption(
    "An autonomous agent that discovers scale-ups matching TVB's target "
    "profile: $1M-$5M revenue/funding, tech platform, minimal-to-no US "
    "presence, with a named CEO/co-founder and a verified email."
)

with st.sidebar:
    st.header("Configuration")

    anthropic_key_input = st.text_input(
        "Anthropic API key (for extraction)",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        type="password",
        help="Used to read scraped website text and pull out structured "
        "company/contact info. Required for meaningful results.",
    )
    serper_key_input = st.text_input(
        "Serper.dev API key (optional)",
        value=os.environ.get("SERPER_API_KEY", ""),
        type="password",
        help="Optional. If provided, Google-backed search is used instead "
        "of the free DuckDuckGo backend for higher-quality discovery.",
    )
    if anthropic_key_input:
        os.environ["ANTHROPIC_API_KEY"] = anthropic_key_input
    if serper_key_input:
        os.environ["SERPER_API_KEY"] = serper_key_input

    st.divider()
    min_leads = st.number_input(
        "Minimum qualifying leads", min_value=5, max_value=100,
        value=config.MIN_QUALIFYING_LEADS, step=5,
    )
    max_domains = st.number_input(
        "Max company sites to scan", min_value=20, max_value=400,
        value=config.MAX_DOMAINS_TO_SCAN, step=10,
    )
    max_queries = st.number_input(
        "Max discovery queries", min_value=10, max_value=200,
        value=config.MAX_SEARCH_QUERIES, step=5,
    )

    run_clicked = st.button("▶ Run agent", type="primary", use_container_width=True)

if "leads" not in st.session_state:
    st.session_state.leads = []

if run_clicked:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.error(
            "An Anthropic API key is required so the agent can read company "
            "pages and extract structured info. Add one in the sidebar."
        )
    else:
        st.session_state.leads = []
        progress_bar = st.progress(0, text="Starting...")
        log_box = st.expander("Live agent log", expanded=True)
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
                log_box.code("\n".join(log_lines[-200:]), language=None)
            elif etype == "progress":
                pct = min(1.0, event["scanned"] / max(1, event["total"]))
                progress_bar.progress(
                    pct, text=f"Scanned {event['scanned']}/{event['total']} sites"
                )
            elif etype == "lead":
                st.session_state.leads.append(event["record"])
                df = pd.DataFrame(st.session_state.leads)
                results_placeholder.dataframe(df, use_container_width=True)
            elif etype == "done":
                st.session_state.leads = event["leads"]
                progress_bar.progress(1.0, text="Done")

        st.success(f"Run complete — {len(st.session_state.leads)} qualifying leads found.")

if st.session_state.leads:
    st.subheader("Qualifying leads")
    df = pd.DataFrame(st.session_state.leads)
    st.dataframe(df, use_container_width=True)
    st.download_button(
        "⬇ Download CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="tvb_qualifying_leads.csv",
        mime="text/csv",
    )
else:
    st.info("Configure your API key(s) in the sidebar, then click **Run agent**.")

with st.expander("How this agent decides a lead qualifies"):
    st.markdown(
        """
1. **Discovery** — generates dozens of search queries by combining TVB's
   Orbit sectors (healthcare, edtech, applied AI, cybersecurity, digital
   twin, fintech, travel, general B2B SaaS) with non-US regions and
   funding/revenue signal phrases, plus a batch of LLM-brainstormed queries
   for angles templates miss.
2. **Scraping** — visits each newly-discovered company's homepage plus
   likely about/team/contact pages.
3. **Extraction** — an LLM reads the page text and returns structured
   fields (industry, HQ, funding/revenue evidence, named contact, email),
   explicitly instructed to leave a field blank rather than guess.
4. **Validation** — the agent only keeps a lead if *all* of these hold:
   funding/revenue evidence falls between $1M-$5M, it's a tech platform,
   there's no clear significant US presence, a named CEO/co-founder is
   present, and their email passes a DNS/MX check (and isn't a generic
   inbox with no name attached).
        """
    )
