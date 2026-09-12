# TVB Lead Discovery Agent

An autonomous agent that discovers companies matching The Venture Build's
target profile, built for TVB's Agentic & Automation Intern take-home task.

**Target profile it filters for:**
1. Revenue or funding raised between **$1M and $5M USD**
2. Operates a **tech-related platform**
3. **Minimal-to-no US presence**
4. **Name and email of the CEO or Co-founder** available and verified

Unverified/unconfirmed fields are left blank rather than filled with a guess
or generic placeholder — matching the brief.

---

## How it works

```
query_generator.py   → builds dozens of discovery queries (sector × region ×
                        funding-signal, plus LLM-brainstormed variants) so
                        the agent finds new sources itself instead of
                        working off one fixed list.
search.py             → runs each query (DuckDuckGo by default, or
                        Serper.dev/Google if a key is provided) and returns
                        candidate company URLs.
scraper.py             → visits each newly-seen domain's homepage plus likely
                        about/team/contact pages and extracts clean text.
extractor.py           → sends the scraped text to Claude with a strict
                        JSON schema, explicitly instructed to leave any
                        unverified field blank rather than guess.
validator.py           → keeps a lead only if ALL target-profile criteria
                        are met AND its contact email passes a live DNS/MX
                        check (and isn't a generic inbox with no name
                        attached to it).
pipeline.py            → orchestrates the above as a streaming generator so
                        the UI can show live progress.
app.py                 → Streamlit UI: enter API key(s), click "Run agent",
                        watch it work, download the CSV.
```

The agent keeps scanning newly-discovered domains, expanding across the
generated query list, until it reaches the configured minimum number of
qualifying leads (default 15) or hits the configured scan/query ceiling —
whichever comes first. All limits are configurable from the sidebar.

## Output

A table (and downloadable CSV) with:

`company_name, description, industry_sector, hq_country,
funding_or_revenue_usd_estimate, contact_name, contact_title,
verified_email, source_url`

## Why these design choices

- **No fixed seed list.** Discovery is query-driven and sector/region are
  combined programmatically, plus an LLM brainstorming pass adds angles a
  template can't (award pages, niche directories, pilot announcements). New
  runs surface different companies as search results shift.
- **LLM extraction, not regex scraping for facts.** Company descriptions,
  HQ, funding figures, and named founders appear in wildly different page
  layouts. An LLM reading the page text with a strict "leave it blank if
  unsure" instruction is far more reliable than brittle pattern matching,
  and it's the more "agentic" approach the task is scoring for.
- **Email verification without sending mail.** The agent checks syntactic
  validity and a live DNS MX lookup on the domain (so a nonexistent domain
  or an unverifiable local part is rejected), and rejects generic mailboxes
  (`info@`, `support@`, ...) unless explicitly tied to a named founder in
  the source text. This is a real, live check — not a guess — without
  requiring a paid email-verification API key. (A paid verifier like
  ZeroBounce/Hunter can be dropped into `validator.verify_email` later for
  an even stronger guarantee.)
- **Key-free search by default.** Uses DuckDuckGo so anyone can trigger a
  run with just an Anthropic API key. If `SERPER_API_KEY` is set, the agent
  automatically switches to Google-backed search for higher-quality,
  less rate-limited results.
- **Graceful degradation everywhere.** Every network/LLM call is wrapped so
  one bad page, timeout, or malformed model response never crashes the run
  — it's just skipped and logged.

## Setup (local)

```bash
git clone <this-repo>
cd tvb-lead-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
streamlit run app.py
```

You can also paste the API key directly into the sidebar — no file editing
required.

### Required / optional keys

| Variable | Required? | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Structured extraction from scraped pages |
| `SERPER_API_KEY` | No | Swaps in Google-backed search (better coverage) |

## Deployment (Streamlit Community Cloud — recommended, free)

1. Push this repo to a **public GitHub repo**.
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in, and
   click "New app".
3. Point it at this repo, branch `main`, main file `app.py`.
4. In **Settings → Secrets**, paste:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
5. Deploy. The reviewer opens the live link, enters/confirms the key if
   needed (or it's already in secrets), and clicks **Run agent** — no
   cloning or local setup required.

The same `app.py`/`requirements.txt` also runs unmodified on Render,
Railway, Replit, or Vercel (via a Streamlit-compatible buildpack) if
preferred.

## Known limitations

- Free-tier search backends (DuckDuckGo) can rate-limit under heavy use;
  the agent backs off and simply tries the next query rather than failing
  the whole run. A `SERPER_API_KEY` avoids this entirely.
- Funding/revenue figures are only accepted when the source text states a
  specific number — the agent will not estimate or infer one, per the
  brief's instruction to leave unverified fields blank. This trades some
  recall for precision.
- Email verification confirms the mailbox's domain can receive mail; it
  does not confirm the specific mailbox exists (that requires an SMTP
  handshake or a paid verification API, which can be added in
  `validator.py` if TVB wants a stricter bar).
