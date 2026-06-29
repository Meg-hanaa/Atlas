"""
Atlas — Streamlit frontend for the Atlas FastAPI backend.

Run the API first:  uvicorn api.main:app --reload
Then the UI:        streamlit run app.py
"""

from __future__ import annotations

import os
import sys
import uuid

import streamlit as st

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: F401 — SSL certs bootstrap

from config import get_subject
from routing.models import format_ai_meta
from ui.api_client import AtlasApiError, AtlasClient
from voice.meta import format_session_cost

st.set_page_config(page_title="Atlas", page_icon="🗺️", layout="wide")

SUBJECT = get_subject()
API_URL = os.getenv("ATLAS_API_URL", "http://127.0.0.1:8000")


def show_meta(
    model_used: str,
    cost: float,
    recall_strength: float | None = None,
    *,
    voice_used: bool = False,
    stt_seconds: float | None = None,
    tts_chars: int | None = None,
):
    st.caption(
        format_session_cost(
            cost,
            model_used=model_used,
            recall_strength=recall_strength,
            voice_used=voice_used,
            stt_seconds=stt_seconds,
            tts_chars=tts_chars,
        )
    )


# --- Session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_card" not in st.session_state:
    st.session_state.current_card = None
if "notes_cache" not in st.session_state:
    st.session_state.notes_cache = None
if "roadmap_cache" not in st.session_state:
    st.session_state.roadmap_cache = None
if "graph_cache" not in st.session_state:
    st.session_state.graph_cache = None
if "graph_html" not in st.session_state:
    st.session_state.graph_html = None
if "mentor_session_id" not in st.session_state:
    st.session_state.mentor_session_id = uuid.uuid4().hex[:12]
if "interview_step" not in st.session_state:
    st.session_state.interview_step = None
if "interview_audio" not in st.session_state:
    st.session_state.interview_audio = None
if "auth_token" not in st.session_state:
    st.session_state.auth_token = None

AUTH_DISABLED = os.getenv("ATLAS_AUTH_DISABLED", "").lower() in ("1", "true", "yes")
GOOGLE_OAUTH_ENABLED = bool(os.getenv("ATLAS_GOOGLE_OAUTH_CLIENT_ID"))

if not AUTH_DISABLED and not st.session_state.auth_token:
    oauth_token = st.query_params.get("oauth_token")
    if oauth_token:
        st.session_state.auth_token = oauth_token
        st.query_params.clear()
        st.rerun()

if not AUTH_DISABLED and not st.session_state.auth_token:
    st.subheader("Sign in to Atlas")
    auth_client = AtlasClient(base_url=API_URL, session_id=st.session_state.mentor_session_id)

    query = st.query_params
    default_verify = query.get("verify", "")
    default_reset = query.get("reset", "")

    auth_mode = st.radio(
        "Account",
        ["Log in", "Register", "Verify email", "Forgot / reset password"],
        horizontal=True,
        label_visibility="collapsed",
    )

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if auth_mode == "Verify email":
        verify_token = st.text_input("Verification token", value=default_verify)
        if st.button("Verify email", type="primary") and verify_token:
            try:
                auth_client.verify_email(verify_token)
                st.success("Email verified — you can log in now.")
            except AtlasApiError as e:
                st.error(str(e))
        if st.button("Resend verification email") and email:
            try:
                auth_client.request_verify(email)
                st.info("Verification email sent (check console if using console backend).")
            except AtlasApiError as e:
                st.error(str(e))

    elif auth_mode == "Forgot / reset password":
        reset_token = st.text_input("Reset token (from email)", value=default_reset)
        new_password = st.text_input("New password", type="password")
        col_forgot, col_reset = st.columns(2)
        if col_forgot.button("Send reset email") and email:
            try:
                auth_client.forgot_password(email)
                st.info("Reset email sent (check console if using console backend).")
            except AtlasApiError as e:
                st.error(str(e))
        if col_reset.button("Reset password", type="primary") and reset_token and new_password:
            try:
                auth_client.reset_password(reset_token, new_password)
                st.success("Password updated — log in with your new password.")
            except AtlasApiError as e:
                st.error(str(e))

    else:
        col_login, col_reg = st.columns(2)
        if col_login.button("Log in", type="primary") and email and password:
            try:
                st.session_state.auth_token = auth_client.login(email, password)
                st.rerun()
            except AtlasApiError as e:
                st.error(str(e))
        if col_reg.button("Register") and email and password:
            try:
                auth_client.register(email, password)
                st.session_state.auth_token = auth_client.login(email, password)
                st.success("Account created — check email/console for verification token.")
                st.rerun()
            except AtlasApiError as e:
                st.error(str(e))

        if GOOGLE_OAUTH_ENABLED:
            st.divider()
            st.link_button(
                "Sign in with Google",
                f"{API_URL.rstrip('/')}/auth/google/start",
                type="secondary",
            )
            st.caption(
                "Uses your Google account. If you already have an email/password account "
                "with the same address, Google will be linked automatically."
            )

    st.caption(
        f"API: `{API_URL}` — tokens print to the API console when `ATLAS_EMAIL_BACKEND=console`."
    )
    st.stop()

api = AtlasClient(
    base_url=API_URL,
    session_id=st.session_state.mentor_session_id,
    token=st.session_state.auth_token,
)

st.title("🗺️ Atlas")
st.caption(f"Subject: `{SUBJECT}` · API: `{API_URL}`")

# Sidebar: ingestion + config status
with st.sidebar:
    st.header("Ingest sources")
    try:
        health = api.health(SUBJECT)
        if health.get("hindsight_ok"):
            st.success("Hindsight connected")
        else:
            st.error("Hindsight not configured — check `.env`")
            st.stop()
    except AtlasApiError as e:
        st.error(f"API unreachable ({e}). Start with: `uvicorn api.main:app --reload`")
        st.stop()

    if st.button("Ingest demo sources", type="primary"):
        with st.spinner("Ingesting YouTube, PDF, photos, LeetCode…"):
            result = api.ingest_demo(SUBJECT)
        st.session_state.notes_cache = None
        st.success(f"Retained {result['retained_count']} chunks to Hindsight")
        if result.get("queued_photos"):
            st.warning(f"{result['queued_photos']} photo(s) queued for OCR review (low confidence)")
        for err in result.get("errors", []):
            st.warning(err)

    st.divider()
    st.subheader("Manual ingest")
    yt_url = st.text_input("YouTube URL")
    if st.button("Ingest YouTube") and yt_url:
        r = api.ingest_youtube(yt_url, SUBJECT)
        st.success(f"Ingested {r['source']}")

    pdf_path = st.text_input("PDF path")
    if st.button("Ingest PDF") and pdf_path:
        r = api.ingest_pdf(pdf_path, SUBJECT)
        st.success(f"Ingested {r['source']}")

    photo_path = st.text_input("Photo path")
    if st.button("Ingest photo (OCR)") and photo_path:
        r = api.ingest_photo(photo_path, SUBJECT)
        if r.get("status") == "ok":
            st.success(f"Ingested {r['source']} (confidence {r['confidence']:.0%})")
        else:
            st.warning(f"Low confidence ({r['confidence']:.0%}) — queued (#{r['queue_id']})")

    lc_text = st.text_area("LeetCode prompt")
    lc_title = st.text_input("LeetCode title (optional)")
    if st.button("Ingest LeetCode") and lc_text:
        r = api.ingest_leetcode(lc_text, lc_title or None, SUBJECT)
        st.success(f"Ingested {r['source']}")

    st.divider()
    st.subheader("OCR review queue")
    pending = api.review_list(SUBJECT)
    if pending:
        st.caption(f"{len(pending)} item(s) awaiting approval")
        for item in pending[:5]:
            with st.expander(f"#{item['id']} {item['source']} ({item['confidence']:.0%})"):
                st.markdown(f"**Reason:** {item['reason']}")
                st.text_area("Pass 1", item["transcription"], key=f"p1_{item['id']}", height=100)
                if item.get("alt_transcription"):
                    st.text_area("Pass 2", item["alt_transcription"], key=f"p2_{item['id']}", height=100)
                edited = st.text_area(
                    "Edit before approve",
                    item["transcription"],
                    key=f"edit_{item['id']}",
                    height=120,
                )
                c1, c2 = st.columns(2)
                if c1.button("Approve", key=f"ok_{item['id']}"):
                    api.review_approve(item["id"], edited, SUBJECT)
                    st.success(f"Approved and retained {item['source']}")
                    st.rerun()
                if c2.button("Reject", key=f"no_{item['id']}"):
                    api.review_reject(item["id"])
                    st.info("Rejected")
                    st.rerun()
    else:
        st.caption("No pending OCR reviews")

    st.divider()
    if st.button("Refresh consolidated notes"):
        st.session_state.notes_cache = None
    if st.button("Seed concepts → scheduler"):
        r = api.seed_concepts(SUBJECT)
        st.success(f"Seeded {r['seeded']} new concepts")
    if st.button("Seed SYNTHETIC demo reviews"):
        r = api.seed_demo_reviews(SUBJECT)
        st.info(r.get("message", "Done"))

    if st.session_state.auth_token:
        if st.button("Log out"):
            st.session_state.auth_token = None
            st.rerun()

summary = api.revision_today(SUBJECT)
col1, col2, col3 = st.columns(3)
col1.metric("Due today", summary["due_count"])
col2.metric("Est. time", f"{summary['estimate_minutes']} min")
col3.metric("Difficulty", summary["difficulty"])

for nudge in api.mentor_nudges(SUBJECT):
    col_msg, col_btn = st.columns([5, 1])
    with col_msg:
        st.warning(f"**Mentor nudge:** {nudge['message']}")
    with col_btn:
        if st.button("Got it", key=f"mentor_ack_{nudge['category']}"):
            api.mentor_acknowledge(nudge["category"], SUBJECT)
            st.rerun()
    if nudge.get("mistake_snippet"):
        with st.expander(f"Full mistake pattern — {nudge['category']}"):
            st.markdown(nudge["mistake_snippet"])

concepts_all = api.list_concepts(SUBJECT)
if concepts_all:
    with st.expander("Knowledge heatmap", expanded=False):
        by_cat: dict[str, list] = {}
        for c in concepts_all:
            by_cat.setdefault(c["category"], []).append(c)
        for cat, items in by_cat.items():
            st.markdown(f"**{cat}**")
            for c in items:
                st.progress(min(1.0, c["recall_strength"]), text=f"{c['name']} ({c['recall_strength']:.0%})")

tab_notes, tab_roadmap, tab_graph, tab_chat, tab_flash, tab_interview, tab_analytics, tab_assess, tab_export = st.tabs(
    [
        "Notes",
        "Roadmap",
        "Concept Graph",
        "Search & Chat",
        "Flashcards & Quiz",
        "Mock Interview",
        "Analytics",
        "Assessments",
        "Export",
    ]
)

with tab_notes:
    st.subheader("Consolidated notes")
    st.caption("Generated by Hindsight `reflect()` — categorized with source attribution")
    if st.button("Generate / refresh notes", key="gen_notes"):
        with st.spinner("Reflecting on your memories (background job)…"):
            st.session_state.notes_cache = api.get_notes_async(SUBJECT)
    if st.session_state.notes_cache:
        st.markdown(st.session_state.notes_cache)
    else:
        st.info("Click **Generate / refresh notes** after ingesting sources.")

with tab_roadmap:
    st.subheader("Learning roadmap")
    st.caption("Diffs your concepts against `curricula/ml.json` — **edit that file** to match your goals")
    diff = api.roadmap_diff(SUBJECT)
    st.metric("Curriculum coverage", f"{diff['coverage_pct']}%")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Covered**")
        for t in diff["covered"]:
            st.markdown(f"- {t['name']}")
    with col_b:
        st.markdown("**Missing**")
        for t in diff["missing"]:
            st.markdown(f"- {t['name']}")
    if st.button("Generate roadmap narrative (reflect)"):
        with st.spinner("Reflecting on gaps (background job)…"):
            st.session_state.roadmap_cache = api.roadmap_narrative_async(SUBJECT)
    if st.session_state.get("roadmap_cache"):
        st.markdown(st.session_state.roadmap_cache)

with tab_graph:
    st.subheader("Concept dependency graph")
    st.warning(
        "Suggested prerequisites from reflect() — **LLM judgment, not ground truth**. "
        "Inspect before relying on it."
    )
    if st.button("Generate prerequisite graph"):
        with st.spinner("Inferring prerequisites (background job)…"):
            payload = api.graph_prerequisites_async(SUBJECT)
            st.session_state.graph_cache = payload["graph"]
            st.session_state.graph_html = payload["html"]
            st.session_state.graph_stats = payload["stats"]
    if st.session_state.get("graph_cache"):
        stats = st.session_state.get("graph_stats") or {}
        st.caption(f"{stats.get('node_count', 0)} nodes · {stats.get('edge_count', 0)} edges · DAG: {stats.get('is_dag', True)}")
        st.components.v1.html(st.session_state.graph_html, height=520, scrolling=True)

with tab_chat:
    st.subheader("Search")
    search_q = st.text_input("Search your notes", key="search_q")
    if search_q:
        for h in api.search(search_q, SUBJECT):
            st.markdown(f"- {h}")

    st.subheader("Chat")
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("meta"):
                st.caption(msg["meta"])

    user_q = st.chat_input("Ask about your notes…")
    if user_q:
        st.session_state.chat_history.append({"role": "user", "content": user_q})
        with st.spinner("Thinking…"):
            resp = api.chat(user_q, SUBJECT)
        meta = format_ai_meta(resp["model_used"], resp["total_cost"])
        st.session_state.chat_history.append({"role": "assistant", "content": resp["answer"], "meta": meta})
        st.rerun()

    with st.expander("Cross-category connections (reflect)", expanded=False):
        st.caption(
            "Compares two **categories** within your ML bank as a stand-in for cross-subject reflect. "
            "Pick concepts from different topic areas to see how reflect() links them."
        )
        by_cat = api.concepts_by_category(SUBJECT)
        cats = sorted(by_cat.keys())
        if len(cats) < 2:
            st.info("Need concepts in at least two categories — generate notes and seed concepts first.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                cat_a = st.selectbox("Category A", cats, key="xcat_a")
                names_a = [c["name"] for c in by_cat[cat_a]]
                concept_a = st.selectbox("Concept A", names_a, key="xconcept_a")
            with col2:
                cat_b = st.selectbox("Category B", [c for c in cats if c != cat_a] or cats, key="xcat_b")
                names_b = [c["name"] for c in by_cat[cat_b]]
                concept_b = st.selectbox("Concept B", names_b, key="xconcept_b")
            if st.button("Explore connection", key="xcat_reflect"):
                with st.spinner("Reflecting across categories…"):
                    st.session_state.cross_cat_cache = api.cross_category_reflect(
                        cat_a, concept_a, cat_b, concept_b, SUBJECT
                    )
            if st.session_state.get("cross_cat_cache"):
                st.markdown(st.session_state.cross_cat_cache)

with tab_flash:
    concepts = api.list_concepts(SUBJECT)
    if not concepts:
        st.info("Seed concepts from sidebar after generating notes.")
    else:
        names = {f"{c['name']} ({c['category']})": c for c in concepts}
        pick = st.selectbox("Concept", list(names.keys()))
        concept = names[pick]

        if st.button("Generate flashcard"):
            with st.spinner("Drafting flashcard (cascadeflow quality routing)…"):
                card = api.generate_flashcard(SUBJECT, concept["id"])
                st.session_state.current_card = card
            if card.get("cascaded"):
                st.caption("Draft escalated to stronger model — FSRS difficulty nudged (Hard signal)")

        card = st.session_state.current_card
        if card:
            st.markdown(f"**Q:** {card['question']}")
            show_meta(card["model_used"], card["total_cost"], concept["recall_strength"])

            with st.expander("Reveal answer"):
                st.markdown(card["answer"])

            st.subheader("Quiz mode")
            user_ans = st.text_area("Your answer")
            knew_well = st.checkbox("I knew this well (Easy)", value=False)
            if st.button("Submit answer"):
                grade = api.submit_quiz(
                    concept_id=concept["id"],
                    question=card["question"],
                    expected_answer=card["answer"],
                    user_answer=user_ans,
                    knew_well=knew_well,
                    subject=SUBJECT,
                )
                st.markdown(f"**{grade['verdict'].upper()}** — {grade.get('feedback', '')}")
                show_meta(grade["model_used"], grade["total_cost"], grade.get("recall_strength"))

with tab_interview:
    st.subheader("Mock Interview")
    st.caption("Targets weak concepts (recall_strength < 0.6) with reflect() + cascadeflow")
    voice_mode = st.checkbox(
        "Voice mode (local faster-whisper STT + Piper TTS — $0, no API keys)",
        value=False,
        key="interview_voice_mode",
    )
    if voice_mode:
        st.caption("First use downloads Piper voice to `data/piper_voices/` (~15 MB). Runs fully offline.")
    weak = api.weak_concepts(SUBJECT, threshold=0.6)
    if not weak:
        st.info("No weak concepts right now — run **Seed SYNTHETIC demo reviews** or quiz yourself first.")
    else:
        weak_sorted = sorted(weak, key=lambda c: c["recall_strength"])
        labels = [f"{c['name']} (strength {c['recall_strength']:.2f})" for c in weak_sorted]
        pick_w = st.selectbox("Weak concept", labels)
        chosen = weak_sorted[labels.index(pick_w)]
        if st.button("Start interview step"):
            with st.spinner("Reflecting on mistakes + routing interview…"):
                step = api.interview_start(SUBJECT, chosen["id"], voice=voice_mode)
                st.session_state.interview_step = step
                st.session_state.interview_audio = None
                if step.get("audio_base64"):
                    st.session_state.interview_audio = {
                        "audio_bytes": AtlasClient.decode_audio(step["audio_base64"]),
                        "chars": step.get("tts_chars"),
                    }

        step = st.session_state.interview_step
        if step and step.get("concept_id") == chosen["id"]:
            st.markdown(step["content"])
            voice_meta = {"voice_used": False}
            if voice_mode and st.session_state.interview_audio:
                st.audio(st.session_state.interview_audio["audio_bytes"], format="audio/wav")
                voice_meta = {"voice_used": True, "tts_chars": st.session_state.interview_audio["chars"]}
            show_meta(step["model_used"], step["total_cost"], step["recall_strength"], **voice_meta)
            with st.expander("Surfaced mistakes (reflect)"):
                st.markdown(step["mistakes"])
            st.caption(f"Mode: **{step['mode']}** ({'quick check' if step['mode'] == 'quick_check' else 'full re-teach'})")

            if voice_mode:
                st.subheader("Your spoken answer")
                audio_input = st.audio_input("Record your answer", key="interview_mic")
                if st.button("Submit spoken answer", key="interview_voice_submit"):
                    if not audio_input:
                        st.warning("Record an answer first.")
                    else:
                        fname = getattr(audio_input, "name", None) or "answer.wav"
                        with st.spinner("Transcribing locally (faster-whisper)…"):
                            stt = api.transcribe_audio(audio_input.getvalue(), fname)
                        transcript = stt["text"]
                        st.markdown(f"**Transcript:** {transcript or '(empty)'}")
                        if not transcript.strip():
                            st.error("Could not transcribe audio — try speaking closer to the mic.")
                        else:
                            with st.spinner("Grading answer…"):
                                grade = api.interview_answer(
                                    SUBJECT,
                                    concept_id=chosen["id"],
                                    question=step["content"],
                                    answer=transcript,
                                    interview_llm_cost=step["total_cost"],
                                    voice_feedback=True,
                                )
                            st.markdown(f"**{grade['verdict'].upper()}** — {grade.get('feedback', '')}")
                            show_meta(
                                grade["model_used"],
                                grade["total_cost"],
                                grade.get("recall_strength"),
                                voice_used=True,
                                stt_seconds=stt["duration_seconds"],
                                tts_chars=st.session_state.interview_audio["chars"]
                                if st.session_state.interview_audio
                                else None,
                            )
                            if grade.get("feedback_audio_base64"):
                                st.audio(
                                    AtlasClient.decode_audio(grade["feedback_audio_base64"]),
                                    format="audio/wav",
                                )
            else:
                text_ans = st.text_area("Your answer (text)", key="interview_text_ans")
                if st.button("Submit text answer", key="interview_text_submit") and text_ans.strip():
                    with st.spinner("Grading answer…"):
                        grade = api.interview_answer(
                            SUBJECT,
                            concept_id=chosen["id"],
                            question=step["content"],
                            answer=text_ans,
                            interview_llm_cost=step["total_cost"],
                        )
                    st.markdown(f"**{grade['verdict'].upper()}** — {grade.get('feedback', '')}")
                    show_meta(
                        grade["model_used"],
                        grade["total_cost"],
                        grade.get("recall_strength"),
                    )

with tab_analytics:
    st.subheader("Analytics dashboard")
    st.caption("FSRS review history, cascadeflow costs, and recall heatmap")
    if st.button("Refresh analytics", key="refresh_analytics"):
        st.session_state.analytics_cache = api.analytics_dashboard(SUBJECT)
    if "analytics_cache" not in st.session_state:
        with st.spinner("Loading analytics…"):
            st.session_state.analytics_cache = api.analytics_dashboard(SUBJECT)
    dash = st.session_state.analytics_cache
    costs = dash.get("costs", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Concepts", dash.get("concept_count", 0))
    c2.metric("Reviews logged", dash.get("review_count", 0))
    c3.metric("Total AI cost", f"${costs.get('total_cost_usd', 0):.4f}")
    c4.metric("Cascade escalations", costs.get("cascade_count", 0))

    st.markdown("**Cascadeflow cost over time**")
    by_day = costs.get("cost_by_day", [])
    if by_day:
        st.bar_chart({row["date"]: row["cost_usd"] for row in by_day})
    else:
        st.info("No cost events yet — chat or generate flashcards to populate.")

    st.markdown("**Cheap vs strong model split**")
    split_cols = st.columns(2)
    split_cols[0].metric("Cheap model cost", f"${costs.get('cheap_cost_usd', 0):.4f}", f"{costs.get('cheap_calls', 0)} calls")
    split_cols[1].metric("Strong model cost", f"${costs.get('strong_cost_usd', 0):.4f}", f"{costs.get('strong_calls', 0)} calls")

    st.markdown("**FSRS retrievability over time**")
    timelines = dash.get("retrievability_timelines", [])
    if timelines:
        for series in timelines[:8]:
            pts = series.get("points", [])
            if not pts:
                continue
            name = pts[0].get("concept_name", f"Concept {series.get('concept_id')}")
            chart_data = {
                p["review_datetime"][:10]: p.get("retrievability") or 0.0
                for p in pts
                if p.get("retrievability") is not None
            }
            if chart_data:
                with st.expander(name):
                    st.line_chart(chart_data)
    else:
        st.info("Review flashcards or run demo reviews to build FSRS history.")

    st.markdown("**Historical recall heatmap**")
    heatmap = dash.get("heatmap", [])
    if heatmap:
        import pandas as pd

        df = pd.DataFrame(heatmap)
        df["recall_pct"] = (df["recall_strength"] * 100).round(0).astype(int)
        st.dataframe(
            df[["category", "name", "recall_pct", "last_reviewed"]].rename(
                columns={"recall_pct": "recall %"}
            ),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("Seed concepts and review them to populate the heatmap.")

with tab_assess:
    st.subheader("Skill assessments")
    st.caption("5–10 question category exams — graded on the strong model only")
    categories = api.assessment_categories(SUBJECT)
    if not categories:
        st.info("Generate notes and seed concepts first.")
    else:
        cat = st.selectbox("Category", categories, key="assess_cat")
        n_q = st.slider("Questions", 5, 10, 7, key="assess_n")
        if st.button("Generate exam", key="gen_assess"):
            with st.spinner("Drafting assessment (strong model)…"):
                st.session_state.assessment = api.generate_assessment(SUBJECT, cat, n_q)
        assessment = st.session_state.get("assessment")
        if assessment and assessment.get("category") == cat:
            st.caption(f"Assessment {assessment.get('assessment_id', '')[:8]}…")
            answers: dict[str, str] = {}
            for q in assessment.get("questions", []):
                st.markdown(f"**{q['id']}.** {q['question']}")
                answers[q["id"]] = st.text_area("Your answer", key=f"assess_{q['id']}", height=80)
            if st.button("Submit for grading", type="primary", key="grade_assess"):
                with st.spinner("Grading (strong model only)…"):
                    result = api.grade_assessment(SUBJECT, assessment, answers)
                st.markdown(f"## {result['verdict']} — average {result['average_score']}%")
                show_meta(result["model_used"], result["total_cost"])
                for g in result.get("graded", []):
                    with st.expander(f"{g['question_id']}: {g.get('score', 0)}% — {g.get('verdict', '')}"):
                        st.markdown(g.get("feedback", ""))

with tab_export:
    st.subheader("Export study guide")
    st.caption("PDF (weasyprint), Obsidian markdown zip, or Anki deck (genanki)")
    col_pdf, col_obs, col_anki = st.columns(3)
    if col_pdf.button("Prepare PDF"):
        with st.spinner("Rendering PDF…"):
            st.session_state.export_pdf = api.export_pdf(SUBJECT)
    if col_obs.button("Prepare Obsidian zip"):
        with st.spinner("Building Obsidian vault…"):
            st.session_state.export_obsidian = api.export_obsidian(SUBJECT)
    if col_anki.button("Prepare Anki deck"):
        with st.spinner("Building Anki deck…"):
            st.session_state.export_anki = api.export_anki(SUBJECT)

    if st.session_state.get("export_pdf"):
        st.download_button(
            "Download PDF",
            st.session_state.export_pdf,
            file_name=f"atlas-{SUBJECT}.pdf",
            mime="application/pdf",
        )
    if st.session_state.get("export_obsidian"):
        st.download_button(
            "Download Obsidian zip",
            st.session_state.export_obsidian,
            file_name=f"atlas-{SUBJECT}-obsidian.zip",
            mime="application/zip",
        )
    if st.session_state.get("export_anki"):
        st.download_button(
            "Download Anki deck",
            st.session_state.export_anki,
            file_name=f"atlas-{SUBJECT}.apkg",
            mime="application/octet-stream",
        )
