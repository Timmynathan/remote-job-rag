from __future__ import annotations

import sys
from datetime import date
from html import escape
from pathlib import Path

# uv's editable install occasionally marks its generated .pth file with the
# macOS "hidden" flag on relink, which site.py silently skips - Streamlit
# runs this file directly (not through the console-script wrapper), so
# adding src/ to sys.path here makes the dashboard immune to that regardless
# of the .pth file's state.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import yaml
import streamlit as st
from dotenv import load_dotenv

from job_hunter import db
from job_hunter.cli import DEFAULT_CV_PATH, DEFAULT_DB_PATH, DEFAULT_PREFERENCES_PATH
from job_hunter.cli import run as run_agent
from job_hunter.pdf_export import export_jobs_to_pdf

load_dotenv()

st.set_page_config(page_title="My Job Hunter", page_icon=":material/work:", layout="wide")

# Streamlit's theme.font config only sets *which* family name to use - it
# doesn't fetch the actual webfont. This loads the real font files so that
# name resolves to something real instead of silently falling back.
st.markdown(
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" '
    'rel="stylesheet">',
    unsafe_allow_html=True,
)

_STATUS_OPTIONS = ["reviewed", "applied", "dismissed"]


def get_conn():
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return db.get_connection(DEFAULT_DB_PATH)


def load_preferences() -> dict:
    if DEFAULT_PREFERENCES_PATH.exists():
        return yaml.safe_load(DEFAULT_PREFERENCES_PATH.read_text()) or {}
    return {}


def save_preferences(preferences: dict) -> None:
    DEFAULT_PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_PREFERENCES_PATH.write_text(yaml.safe_dump(preferences, sort_keys=False))


def score_color(score: int | None) -> str:
    if score is None:
        return "gray"
    if score >= 70:
        return "green"
    if score >= 40:
        return "orange"
    return "red"


def card_header_html(title: str, company: str) -> str:
    title = escape(title)
    company = escape(company or "")
    return (
        '<div style="margin-bottom:0.6rem;">'
        f'<div style="font-size:1.2rem;font-weight:700;color:#0F172A;line-height:1.35;'
        f'letter-spacing:-0.01em;">{title}</div>'
        f'<div style="font-size:0.95rem;font-weight:500;color:#64748B;margin-top:0.2rem;">{company}</div>'
        "</div>"
    )


_RAINBOW_GRADIENT = "linear-gradient(120deg, #FF6B6B, #FFD93D, #6BCB77, #4D96FF, #6B46C1)"

# Same glyph as Material Symbols' "auto_awesome" - used inline since the
# :material/...: shortcode only works inside Streamlit's own markdown
# renderer, not in raw HTML passed through unsafe_allow_html.
_SPARKLE_SVG = (
    '<svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" '
    'style="flex-shrink:0;"><path d="M19,9l1.25-2.75L23,5l-2.75-1.25L19,1l-1.25,2.75L15,5l2.75,1.25L19,9z '
    "M11.5,9.5L9,4L6.5,9.5L1,12l5.5,2.5L9,20l2.5-5.5L17,12L11.5,9.5z "
    'M19,15l-1.25,2.75L15,19l2.75,1.25L19,23l1.25-2.75L23,19l-2.75-1.25L19,15z"/></svg>'
)


def reasoning_box_html(reason: str) -> str:
    reason = escape(reason)
    return (
        '<div style="margin:0.85rem 0 1.35rem 0;padding:1.1rem 1.35rem;'
        'border-radius:0.75rem;border:2px solid transparent;background:'
        f"linear-gradient(#FFFFFF, #FFFFFF) padding-box, {_RAINBOW_GRADIENT} border-box;\">"
        '<div style="display:flex;align-items:center;justify-content:flex-end;gap:0.3rem;'
        'color:#94A3B8;font-size:0.65rem;font-weight:500;letter-spacing:0.03em;'
        f'margin-bottom:0.5rem;">{_SPARKLE_SVG}<span>AI GENERATED</span></div>'
        f'<div style="color:#334155;font-size:0.95rem;line-height:1.6;">{reason}</div>'
        "</div>"
    )


conn = get_conn()

st.markdown("## :material/work: My Job Hunter")
st.caption("Remote roles open to Nigeria-based candidates, pulled from 6 job boards and scored against your CV.")

all_jobs = db.list_jobs(conn)
stat_cols = st.columns(4)
stat_cols[0].metric("Total jobs", len(all_jobs))
stat_cols[1].metric("New", sum(1 for j in all_jobs if j.status == "new"))
stat_cols[2].metric("Strong matches", sum(1 for j in all_jobs if (j.match_score or 0) >= 70))
stat_cols[3].metric("Applied", sum(1 for j in all_jobs if j.status == "applied"))

st.divider()

with st.sidebar:
    st.markdown("### :material/work: My Job Hunter")

    with st.expander("CV & Preferences", expanded=not DEFAULT_CV_PATH.exists(), icon=":material/tune:"):
        st.caption(
            "Saving here overwrites config/CV.pdf and config/preferences.yaml directly "
            "(hand-added YAML comments won't survive a save)."
        )
        prefs = load_preferences()

        st.markdown("**CV**")
        if DEFAULT_CV_PATH.exists():
            size_kb = DEFAULT_CV_PATH.stat().st_size / 1024
            st.caption(f"Current CV on file: {size_kb:.0f} KB")
        else:
            st.caption("No CV on file yet.")
        uploaded_cv = st.file_uploader("Upload CV (PDF)", type=["pdf"])

        st.markdown("**Preferences**")
        role_titles_text = st.text_area(
            "Target roles (one per line)",
            value="\n".join(prefs.get("role_titles") or []),
            height=100,
            help="Only postings whose title matches one of these are kept.",
        )
        seniority = st.text_input("Seniority label", value=prefs.get("seniority") or "")
        actual_years_experience = st.number_input(
            "Actual years of experience",
            min_value=0,
            max_value=50,
            value=int(prefs.get("actual_years_experience") or 0),
            help="Overrides whatever your CV states, so scoring doesn't over-estimate seniority.",
        )
        salary_floor_usd = st.number_input(
            "Minimum salary (USD)",
            min_value=0,
            value=int(prefs.get("salary_floor_usd") or 0),
            step=1000,
        )
        nigeria_required = st.checkbox(
            "Require Nigeria eligibility", value=prefs.get("nigeria_required", True)
        )
        exclude_keywords_text = st.text_area(
            "Exclude titles containing (one per line)",
            value="\n".join(prefs.get("exclude_title_keywords") or []),
            height=100,
            help="e.g. senior, staff, lead, principal.",
        )

        if st.button("Save CV & Preferences", width="stretch", icon=":material/save:"):
            if uploaded_cv is not None:
                DEFAULT_CV_PATH.parent.mkdir(parents=True, exist_ok=True)
                DEFAULT_CV_PATH.write_bytes(uploaded_cv.getvalue())

            save_preferences(
                {
                    "role_titles": [line.strip() for line in role_titles_text.splitlines() if line.strip()],
                    "seniority": seniority.strip(),
                    "actual_years_experience": int(actual_years_experience),
                    "salary_floor_usd": int(salary_floor_usd),
                    "nigeria_required": nigeria_required,
                    "exclude_title_keywords": [
                        line.strip() for line in exclude_keywords_text.splitlines() if line.strip()
                    ],
                }
            )
            st.success("Saved.")
            st.rerun()

    _NODE_LABELS = {
        "generate_queries": "Generating search queries",
        "retrieve": "Retrieving postings from all sources",
        "validate_dedupe": "Filtering for role / seniority / eligibility",
        "score": "Scoring against your CV",
    }

    with st.expander("Run Agent", expanded=False, icon=":material/play_arrow:"):
        run_min_strong = st.number_input("Min strong matches", min_value=1, value=5)
        run_max_iterations = st.number_input("Max iterations", min_value=1, max_value=5, value=2)
        run_max_to_score = st.number_input("Max candidates to score", min_value=1, value=15)

        if st.button("Run Agent Now", width="stretch", icon=":material/play_arrow:"):
            status_box = st.status("Starting run...", expanded=True)

            def on_node_complete(node_name: str) -> None:
                status_box.write(f":material/check: {_NODE_LABELS.get(node_name, node_name)}")

            try:
                ranked = run_agent(
                    min_strong_matches=int(run_min_strong),
                    max_iterations=int(run_max_iterations),
                    max_candidates_to_score=int(run_max_to_score),
                    on_node_complete=on_node_complete,
                )
                status_box.update(label=f"Done — {len(ranked)} job(s) in shortlist", state="complete")
                # No st.rerun() here: the job list further down this same
                # script run already re-queries the database, so it picks up
                # fresh results naturally - rerunning would just flash this
                # message away before it's readable.
            except Exception as exc:  # noqa: BLE001 - surface any failure in the UI rather than crashing the app
                status_box.update(label=f"Run failed: {exc}", state="error")

    st.markdown("### :material/tune: Filters")
    status_filter = st.selectbox("Status", ["All", "new", "reviewed", "applied", "dismissed"])
    sources = [row["source"] for row in conn.execute("SELECT DISTINCT source FROM jobs ORDER BY source")]
    source_filter = st.selectbox("Source", ["All", *sources])
    min_score = st.slider("Minimum match score", 0, 100, 0)
    sort_choice = st.selectbox(
        "Sort by",
        ["Score (high to low)", "Score (low to high)", "Posted date (newest)", "Company"],
    )

order_by = {
    "Score (high to low)": "match_score DESC",
    "Score (low to high)": "match_score ASC",
    "Posted date (newest)": "posted_date DESC",
    "Company": "company ASC",
}[sort_choice]

jobs = db.list_jobs(
    conn,
    status=None if status_filter == "All" else status_filter,
    source=None if source_filter == "All" else source_filter,
    min_score=min_score or None,
    order_by=order_by,
)

list_header_col, export_col = st.columns([4, 1], vertical_alignment="center")
with list_header_col:
    st.caption(f"{len(jobs)} job(s)")
with export_col:
    if jobs:
        st.download_button(
            "Export to PDF",
            data=export_jobs_to_pdf(jobs),
            file_name=f"job-shortlist-{date.today().isoformat()}.pdf",
            mime="application/pdf",
            width="stretch",
            icon=":material/download:",
        )

for job in jobs:
    with st.container(border=True):
        title_col, score_col = st.columns([8, 2], vertical_alignment="top")
        with title_col:
            st.markdown(card_header_html(job.title, job.company), unsafe_allow_html=True)
        with score_col:
            if job.match_score is None:
                st.badge("Unscored", color="gray")
            else:
                st.badge(str(job.match_score), color=score_color(job.match_score))

        with st.container(horizontal=True):
            st.badge(job.source, color="gray")
            st.badge(job.remote_type.replace("_", " "), color="primary")
            if job.nigeria_eligible is True:
                st.badge("Nigeria-eligible", color="green")
            elif job.nigeria_eligible is False:
                st.badge("Restricted", color="red")
            if job.salary_min or job.salary_max:
                salary = f"{job.salary_min or '?'}-{job.salary_max or '?'} {job.salary_currency or ''}".strip()
                st.badge(salary, color="violet")
            if job.posted_date:
                st.badge(job.posted_date.isoformat(), color="gray")

        if job.match_reason:
            st.markdown(reasoning_box_html(job.match_reason), unsafe_allow_html=True)

        link_col, status_col = st.columns([1, 3], vertical_alignment="center")
        with link_col:
            st.link_button("View posting", job.url, icon=":material/open_in_new:")
        with status_col:
            current_status = job.status if job.status in _STATUS_OPTIONS else None
            selected_status = st.segmented_control(
                "Status",
                _STATUS_OPTIONS,
                default=current_status,
                key=f"status-{job.job_id}",
                label_visibility="collapsed",
            )
            if selected_status != current_status:
                db.update_status(conn, job.job_id, selected_status or "new")
                st.rerun()
