# My Job Hunter

**A solo, on-demand AI agent that hunts remote job postings open to Nigeria-based candidates, scores them against your CV, and hands you a ranked shortlist — not a hosted product, a tool you run for yourself.**

---

## 1. What it is

Remote job listings for Nigeria-based candidates are scattered across LinkedIn, Indeed, Glassdoor, remote-only boards, and individual companies' own career pages. This agent runs on demand (or on a light personal schedule), searches across all of them in one pass, filters for genuine Nigeria eligibility, checks that each posting is still actually open, scores it against your CV, and gives you a ranked shortlist with reasoning — instead of you manually checking five sites and rereading fifty stale postings.

Because it's built for one person's own use rather than as a service for other users, the design choices are different from a typical product: no persistent multi-user infrastructure, no need to be "always on," and a materially different risk profile for sources like LinkedIn and Indeed — occasional, low-volume, personal-account use is a different pattern than a daily pipeline scraping and redistributing at scale.

---

## 2. High-level architecture

An agent graph (LangGraph-style state machine), not a continuously running pipeline:

```
┌───────────────┐   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ 1. Generate   │──▶│ 2. Retrieve   │──▶│ 3. Validate + │──▶│ 4. Score      │
│    queries    │   │    (multi-    │   │    dedupe     │   │    against    │
│    from CV    │   │    source)    │   │  (Playwright) │   │    CV         │
└───────────────┘   └───────────────┘   └───────────────┘   └───────┬───────┘
        ▲                                                            │
        │              5. Enough good matches?                       │
        └───────────────────── no, refine ◀──────────── yes ─────────┘
                                                            │
                                                            ▼
                                                     Ranked shortlist
                                                     → local dashboard
```

Run manually whenever you're job-hunting, or on a light daily schedule via **launchd** on your own machine (§10) — not a continuous background service, and it only fires when your machine is on.

The refine loop (node 5) is capped at **2 iterations** total — one initial pass plus one broadened retry — to keep API cost/time predictable before finalizing whatever shortlist it has.

---

## 3. Data sources

| Source | Status | Access method | Notes |
|---|---|---|---|
| Remotive | ✅ Built | Free public API, no auth | `search`/`category`/`limit` params verified to NOT filter server-side — fetched as a full feed, filtered client-side instead (§4). |
| Arbeitnow | ✅ Built | Free public API, no auth | Must link back to arbeitnow.com. Only `remote=true` listings are kept. |
| Jobicy | ✅ Built | Free public API, no auth | Credit + link back. Can be slow/time out occasionally — isolated so one failing source doesn't take down the run (§7). |
| RemoteOK | ✅ Built | Free public API, no auth | Must link directly back to the RemoteOK job URL; free feed is 24h delayed. Requires a real browser-like User-Agent or requests stall. |
| Himalayas | ✅ Built | Free public API, no auth | Structured `locationRestrictions`/salary/expiry fields — the most reliable source for eligibility and still-open inference. |
| We Work Remotely | ✅ Built | Official public RSS feed | ToS bans scraping the site but allows commercial/personal use of the RSS feed. Title arrives as "Company: Role" and is split accordingly. |
| LinkedIn, Indeed, Glassdoor | ⏳ Not yet built | **Tavily web search** for discovery, **Playwright** for per-posting validation only | Discovery queries a search index, not the sites directly. Playwright only visits individual known posting URLs to confirm they're still live before scoring — not bulk scraping search-results pages. Reasonable at solo, low-frequency scale; do this logged out of your personal LinkedIn account where possible to avoid any risk to that account. |
| Greenhouse & Lever (direct) | ⏳ Not yet built | Public per-company board APIs, no auth | Planned: a small default list of well-known remote-friendly companies on Greenhouse/Lever; editable via config as you find more you care about. |

**Still excluded:** Wellfound, Arc.dev, Jobberman, Terawork (no legitimate access path or scope mismatch — see prior vetting). **X/Twitter:** intentionally left out for now.

---

## 4. CV matching

- You provide your CV (PDF) plus `config/preferences.yaml` as the source of truth on disk — editable directly, or via the dashboard's CV & Preferences form (§9). Preferences currently include: `role_titles` (e.g. Full Stack/Frontend/Backend/AI Engineer), `seniority`, `actual_years_experience` (overrides whatever the CV states, so the LLM doesn't over-estimate seniority from an inflated CV), `salary_floor_usd`, `nigeria_required`, and `exclude_title_keywords` (senior/staff/lead/principal/etc.).
- `role_titles`, `exclude_title_keywords`, and `nigeria_required` are enforced as **hard filters** in node 3 (validate_dedupe) — non-matching postings are dropped before they ever reach the LLM, not just down-scored.
- That profile feeds **query generation** (node 1) — what roles/keywords to search for — and **scoring** (node 4) — how well each retrieved posting matches you specifically, with `actual_years_experience` injected into both prompts explicitly.
- Matching is pure LLM judgment (Gemini reads the JD against your CV, reasons about fit) — no embedding-similarity pre-filter in the MVP. Scoring is capped at a configurable number of candidates per run (default 15, newest postings prioritized) to stay within free-tier LLM rate limits now that 6 sources feed in.
- Output per job: a 0–100 match score plus a short "why this matches" rationale — not just a relevance-ranked list, an actual judgment call you can sanity-check.

---

## 5. Data model

| Field | Type | Notes |
|---|---|---|
| `job_id` | string | Stable hash of source + native ID |
| `title`, `company`, `location` | string | |
| `remote_type` | enum | `fully_remote` / `hybrid` / `unclear` |
| `nigeria_eligible` | bool | Explicit or inferred |
| `salary_min` / `max` / `currency` | nullable | |
| `posted_date` | date | |
| `source` | string | `linkedin`, `remotive`, `greenhouse:company`, etc. |
| `url` | string | |
| `description` | text | |
| `still_open` | bool | Set by Playwright validation |
| `match_score` | int (0–100) | |
| `match_reason` | text | |
| `status` | enum | `new` / `reviewed` / `applied` / `dismissed` — tracked across runs so you don't re-review the same posting twice |

---

## 6. Storage

No hosted vector database needed at this scale — and none used, since the MVP skips embedding pre-filtering entirely (§4). A local **SQLite** file is enough to persist job records, scores, and your review status between runs — this is what makes each run incremental rather than starting from zero every time.

---

## 7. Agent flow (the 5 nodes)

1. **Generate queries** — from your CV profile + preferences file (role, seniority, salary floor), produce a set of targeted search queries. (Currently unused by the 6 live direct-API sources, since none of them filter server-side by search term — see §3 — but will matter once Tavily/LinkedIn discovery is added.)
2. **Retrieve** — one call per source per pass across all 6 built sources (Remotive/Arbeitnow/Jobicy/RemoteOK/Himalayas/WWR), merged by job_id; each source is isolated so one failing/slow API doesn't take down the run. Tavily (LinkedIn/Indeed/Glassdoor) and Greenhouse/Lever are planned additions.
3. **Validate + dedupe** — sets `still_open` (defaults true for these 6 direct-API sources, since their feeds already reflect current listings; Playwright liveness-checking is reserved for search-index sources once LinkedIn/Indeed/Glassdoor are added), then drops postings failing the role/seniority/geo hard filters from §4.
4. **Score** — Gemini matches each surviving posting against your CV, produces score + reasoning, capped at a per-run scoring budget (§4).
5. **Refine or finish** — if too few strong matches came back, loop to step 1 with broadened/adjusted queries (max 1 retry — 2 iterations total); otherwise finalize the ranked shortlist.

---

## 8. User flow

1. Run the agent — manually via `uv run naija-job-hunter`, from the dashboard's "▶️ Run Agent" button (✅ built), or automatically via the daily launchd job (§10, ✅ built).
2. Agent works through the 5-node graph; the dashboard's run button shows live per-node progress (✅ built, via LangGraph's `stream(..., stream_mode="updates")`). Scheduled runs log to `logs/daily-run.log` / `daily-run.err.log` instead.
3. Email digest after scheduled runs: ✅ built, via Resend. Only fires for postings that are both new-to-the-database and above the strong-match threshold (§7 node 5), so you're not re-notified about the same unreviewed posting every day. No-ops safely if `RESEND_API_KEY`/`DIGEST_TO_EMAIL` aren't set.
4. Dashboard shows the ranked shortlist: score, title, company, source, salary if known, "why this matches." ✅ Built.
5. You review, mark jobs `applied`/`reviewed`/`dismissed` — persisted so future runs don't resurface them. ✅ Built.
6. PDF export of a shortlist: ✅ built, via `reportlab` (pure-Python, no system dependencies — swapped in after `weasyprint` turned out to need Homebrew-installed Pango/cairo).

---

## 9. UI

A local Streamlit dashboard (`dashboard/app.py`), not a public-facing app. React + TypeScript deferred, see §12.

**Built — MVP complete:**
- Ranked list of job cards: score badge, title, company, remote/Nigeria-eligibility tag, source badge, salary if present, link, match reasoning.
- Filter/sort by status, source, minimum score, posted date, company.
- Status controls per job (`reviewed` / `applied` / `dismissed`) that persist to SQLite.
- CV upload and preferences form (writes to `config/CV.pdf` / `config/preferences.yaml`; note a save doesn't preserve hand-added YAML comments).
- "▶️ Run Agent" button with configurable min-strong-matches/max-iterations/max-candidates-to-score, live per-node status, and a results summary on completion.
- "⬇️ Export shortlist to PDF" button for the currently filtered view.

---

## 10. Tech stack

- **Agent orchestration**: LangGraph
- **LLM**: Google Gemini (`gemini-flash-latest` via `langchain-google-genai`), for query generation, scoring, and reasoning — chosen over GPT-4o for its free tier, since OpenAI's API has no ongoing free usage and this is a low-frequency personal tool. Free-tier daily quota (20 requests/day at time of writing) is the main real-world constraint; the per-run scoring cap (§4) manages this.
- **Discovery**: Tavily, for LinkedIn/Indeed/Glassdoor — ⏳ not yet built.
- **Validation**: Playwright, for liveness checks on individual postings — ⏳ not yet built (deferred until search-index sources are added, §7).
- **Direct APIs (✅ built)**: Remotive, Arbeitnow, Jobicy, RemoteOK, Himalayas, We Work Remotely
- **Direct APIs (⏳ not yet built)**: Greenhouse/Lever
- **Storage**: SQLite
- **UI**: Streamlit
- **Scheduling**: ✅ Built via `launchd` (`scripts/launchd/com.naijajobhunter.dailyrun.plist`, installed to `~/Library/LaunchAgents/`), triggering `scripts/run_daily.sh` daily at 8am. Requires Full Disk Access granted to `/bin/bash` (System Settings → Privacy & Security), since `~/Desktop` is otherwise TCC-protected from background/launchd processes.
- **Notifications**: ✅ Built — email digest via **Resend** (`resend` Python SDK), sent after each run for new + strong matches only.
- **PDF export**: ✅ Built — `reportlab` (pure Python, no system dependencies).
- **Python tooling**: uv, for environment and dependency management

This replaces the repo's original Next.js scaffold — this is a pure Python project, not a Next.js app.

---

## 11. Compliance notes

- This is designed for solo, low-frequency, personal use — not a service redistributing data to other users. That distinction matters: LinkedIn's active 2025–2026 litigation has targeted commercial scraping-as-a-service operations selling bulk data at scale (ProAPIs, Proxycurl/Nubela), not individuals running an occasional personal agent.
- LinkedIn/Indeed/Glassdoor coverage comes from a search index (Tavily/JSearch) plus light per-posting validation (Playwright) — not bulk scraping of search-results pages.
- Do the Playwright validation step logged out of your personal LinkedIn account where possible, to avoid any risk of that account being flagged.
- Every open API in §3 has its own light-touch terms (attribution, link-back, polling frequency) — honor them per-source.
- Re-verify source terms periodically; API availability and enforcement patterns in this space change often.

---

## 12. Roadmap / future ideas

- Polished **React + TypeScript** dashboard, once the Streamlit MVP proves the flow out.
- Embedding-similarity pre-filter ahead of LLM scoring, if per-run posting volume grows enough to make it worth the added complexity.
- Move the scheduled run off local launchd onto a small always-on cloud host, if "only runs when your machine is on" becomes a real limitation.
- Slack notification as an alternative/addition to the Resend email digest.
- Salary normalization across currencies for better filtering.
- X/Twitter keyword monitoring as an additional discovery source (evaluated, technically feasible via paid API, deferred for now).
- Auto-drafted cover letter or outreach message per strong match.
- Browser extension to one-click "add this posting" for manual discoveries outside the agent's sources.