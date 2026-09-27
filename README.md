# Businessdev

Enter a product name, get one combined business development report from a CrewAI crew of
three agents.

## Setup

Requires Python 3.10–3.13. Tested on 3.12.

```bash
cd ~/Businessdev
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env      # skip if .env already exists
```

Then fill in `.env`:

```
OPENAI_API_KEY=sk-...
SERPER_API_KEY=...
```

Get a Serper key at https://serper.dev. Restart the app after editing `.env`.

## Run

```bash
.venv/bin/streamlit run app.py
```

Or headless, which is the fastest way to check everything works:

```bash
.venv/bin/python run_cli.py "bamboo home decor"
```

## How it works

Three agents run in sequence, each owning one section of a single report. There is no
separate synthesis step, so the report is a plain concatenation of the three outputs.

| # | Agent | Model | Section |
|---|-------|-------|---------|
| 1 | Market Research Analyst | `gpt-4o-mini` | Market Analysis — size, segments, competitors, demand signals |
| 2 | Technology & Operations Analyst | `gpt-4o-mini` | Technology Analysis — build/source approach, costs, risks, path to launch |
| 3 | Business Development Lead | `gpt-4o` | Business Development Strategy — positioning, pricing, GTM, 90-day plan |

Tasks 2 and 3 receive the prior agents' output as `context`, so the report builds on itself
rather than describing the same product three times from scratch.

Agents 1 and 2 research with Google via Serper. Agent 3 has a search tool too but mostly
synthesizes what it is given.

### Category-agnostic prompts

The prompts tell each agent to classify the input first — software, hardware, physical
consumer good, service, marketplace — and then apply the metrics that fit. A physical
product gets sized by retail category spend, unit economics (COGS, landed cost, gross
margin) and channel margin; software gets sized by paying accounts and ACV. This is why the
same crew handles "bamboo home decor" and "a B2B billing API" without prompt changes.

## Search budget

Serper's free tier is a **one-time** allowance of roughly 2,500 queries, not a monthly
allowance. Each agent is capped at `MAX_SEARCHES_PER_AGENT` (default 4) — 12 per run. When
an agent exhausts its budget the tool returns a message telling it to write the section from
what it already has rather than retrying, so a run cannot silently burn the quota.

Repeated identical queries within a single run are served from a cache, so the three agents
do not pay twice for the same lookup. The cache is cleared between runs; it is not a
cross-run cache.

Adjust in `.env`:

```
SERPER_MAX_RESULTS=8          # results per search
MAX_SEARCHES_PER_AGENT=4      # hard cap per agent
```

## Configuration

All in `.env` (see `.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | — | Required |
| `SERPER_API_KEY` | — | Required |
| `RESEARCH_MODEL` | `gpt-4o-mini` | Model for agents 1 and 2 |
| `WRITER_MODEL` | `gpt-4o` | Model for agent 3 |
| `SERPER_MAX_RESULTS` | `8` | Results per search |
| `MAX_SEARCHES_PER_AGENT` | `4` | Search cap per agent |
| `MAX_RPM` | `20` | CrewAI rate limit |

`.env` is gitignored. Never commit keys.

## Deploy to Streamlit Community Cloud

Free hosting that deploys straight from GitHub. The repo already has what it needs:
`requirements.txt` at the root, `app.py` as the entrypoint, and `.python-version` pinning 3.12.

1. Sign in at https://share.streamlit.io
2. Link your GitHub account (it needs admin access to the repo)
3. **New app → Deploy from GitHub** → pick `VJaw/Businessdev` → branch `main` → entrypoint `app.py`
4. Open **Advanced settings → Secrets** and paste:

   ```toml
   OPENAI_API_KEY = "sk-..."
   SERPER_API_KEY = "..."
   RESEARCH_MODEL = "gpt-4o-mini"
   WRITER_MODEL = "gpt-4o"
   SERPER_MAX_RESULTS = "8"
   MAX_SEARCHES_PER_AGENT = "4"
   MAX_RPM = "20"
   ```

5. Deploy

Secrets go into `st.secrets`, not the process environment, so `bizdev/config.py` reads
`st.secrets` first and only falls back to `.env`. Locally it never touches `st.secrets`, so
`run_cli.py` keeps working off `.env` alone. Real environment variables always win over
`st.secrets`.

Every push to `main` redeploys automatically.

### Before you share the link

The app has no authentication and no rate limiting. Anyone who finds the URL spends your
OpenAI tokens and burns the one-time Serper allowance. Options, in rough order of effort:

- Keep it unlisted, share the URL only with people you trust
- Add a password gate at the top of `app.py` (`st.text_input("password", type="password")`
  compared against a secret) — this stops casual visitors, not a determined attacker
- Put it behind Cloudflare Access or a similar auth proxy
- Switch to a platform with built-in auth, or pay for a Streamlit team plan

Also expect slow cold starts: free-tier apps sleep when idle and take a while to wake.

## Layout

```
app.py                  Streamlit UI
run_cli.py              headless runner
bizdev/
  config.py             env loading, model names, endpoints
  agents.py             the 3 Agent definitions
  tasks.py              the 3 Task definitions, context-chained
  crew.py               crew assembly, run, error mapping
  report.py             markdown assembly and normalisation
  tools/serper.py       SerperSearchTool (crewai.tools.BaseTool)
```

## Notes

`crewai-tools` is deliberately not a dependency. The crew only needs search, so
`bizdev/tools/serper.py` implements it directly and the install stays small. To swap in the
official tool instead, `pip install crewai-tools` and replace the tool instances in
`bizdev/agents.py` with `crewai_tools.SerperDevTool(niche="news")`.

The UI is a blocking run: the browser waits ~1–2 minutes while `st.status` shows which of
the three agents have finished. There is no background job or streaming yet.

Agents are instructed to label anything they could not verify as *(unverified estimate)*
rather than presenting a guess as fact. The report carries that caveat in its header.
