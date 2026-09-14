# My Job Hunter

A solo, on-demand AI agent that hunts remote job postings open to Nigeria-based candidates, scores them against your CV, and hands you a ranked shortlist — not a hosted product, a tool you run for yourself.

Full design rationale, architecture decisions, and roadmap live in [`project-about.md`](./project-about.md). This README is the practical "how do I run it" reference.

## What it does

Remote listings for Nigeria-based candidates are scattered across job boards with wildly inconsistent APIs. This project runs a small agent graph that:

1. Generates targeted search queries from your CV + stated preferences
2. Pulls postings from 6 free job-board APIs in parallel
3. Filters out anything that doesn't match your target roles, is above your seniority ceiling, or isn't genuinely open to Nigeria-based candidates
4. Scores each surviving posting against your CV using an LLM, with reasoning
5. Refines the search once more if too few strong matches came back, then finalizes a ranked shortlist

Results, your CV, and your preferences all live in a shared Postgres database — so a local scheduled run and a dashboard deployed anywhere both read/write the exact same data, and re-runs are incremental (you never re-review the same posting twice).

## Data sources

Currently live: **Remotive, Arbeitnow, Jobicy, RemoteOK, Himalayas, We Work Remotely**.

Planned, not yet built: LinkedIn/Indeed/Glassdoor (via Tavily search + Playwright liveness checks) and direct Greenhouse/Lever pulls. See `project-about.md` §3 for the reasoning and compliance notes.

## Tech stack

- **Agent orchestration**: LangGraph
- **LLM**: Google Gemini (`langchain-google-genai`)
- **HTTP**: httpx
- **Data validation**: Pydantic
- **Storage**: Postgres (Neon) — jobs, CV bytes, and preferences all live here, shared between local runs and any hosted dashboard
- **UI**: Streamlit
- **PDF export**: reportlab
- **Email digest**: Resend
- **Scheduling**: launchd (macOS)
- **Tooling**: uv, pytest

## Setup

```bash
uv sync
cp .env.example .env
```

Fill in `.env`:

| Variable | Required for |
|---|---|
| `DATABASE_URL` | Postgres connection string — get one free from [neon.tech](https://neon.tech): sign up, create a project, copy the connection string from the dashboard |
| `TEST_DATABASE_URL` | A second Postgres URL (a separate free Neon project works well) used only by the test suite — truncated before every test run, so never point this at your real data |
| `GOOGLE_API_KEY` | Gemini (query generation + scoring) |
| `TAVILY_API_KEY` | Reserved for planned LinkedIn/Indeed discovery — not used yet |
| `RESEND_API_KEY` / `DIGEST_TO_EMAIL` / `DIGEST_FROM_EMAIL` | Email digest after each run |

Then upload your CV and set your preferences (target roles, seniority, salary floor, experience level, excluded keywords) through the dashboard's "CV & Preferences" panel — both are stored in Postgres, not local files, so this only needs doing once no matter where you run the dashboard from.

## Running it

**Dashboard:**
```bash
uv run streamlit run dashboard/app.py
```
Opens at `http://localhost:8501`. Browse the shortlist, edit CV/preferences, trigger a run with live per-node progress, and export to PDF.

**CLI only:**
```bash
uv run naija-job-hunter
```
Flags: `--min-strong-matches`, `--max-iterations`, `--max-candidates-to-score`, `--no-notify`.

**Scheduled daily runs** are set up via `launchd` — see `scripts/launchd/com.naijajobhunter.dailyrun.plist` and `scripts/run_daily.sh`. Requires Full Disk Access granted to `/bin/bash` (System Settings → Privacy & Security), since `~/Desktop` is otherwise off-limits to background processes on macOS.

## Development

```bash
uv run pytest tests/ -v
```
LLM and HTTP calls are dependency-injected with fakes, so nothing hits a real API during testing. Database tests need `TEST_DATABASE_URL` set (see Setup above) — they skip cleanly if it's absent, rather than failing.

**Known quirk**: `uv`'s editable install occasionally marks its generated `.pth` file with the macOS "hidden" file flag, which Python's `site.py` silently skips — this shows up as `ModuleNotFoundError: No module named 'job_hunter'` on the CLI (the dashboard is immune to it; pytest is too, via `pythonpath` config). Fix:
```bash
chflags nohidden .venv/lib/python3.12/site-packages/*.pth
```

## Project structure

```
src/job_hunter/
├── graph.py            # LangGraph wiring (the 5-node agent)
├── nodes/               # generate_queries, retrieve, validate_dedupe, score, refine
├── sources/              # one module per job board API
├── models.py            # Job schema
├── db.py                # Postgres persistence (jobs, CV bytes, preferences)
├── cv_parser.py          # PDF text extraction
├── notify.py             # Resend email digest
├── pdf_export.py          # Shortlist → PDF
└── cli.py                # Entrypoint

dashboard/app.py        # Streamlit UI
scripts/                 # launchd scheduling
tests/                   # offline except db.py tests (need TEST_DATABASE_URL)
```
