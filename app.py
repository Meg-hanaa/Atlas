"""
Atlas — Streamlit frontend for the Atlas FastAPI backend.

Run the API first:  uvicorn api.main:app --reload
Then the UI:        streamlit run app.py
"""

from __future__ import annotations

import os
import sys
import uuid
from urllib.parse import urlparse
import base64

import streamlit as st

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: F401 — SSL certs bootstrap

from routing.models import format_ai_meta
from ui.api_client import AtlasApiError, AtlasClient
from voice.meta import format_session_cost

st.set_page_config(page_title="Atlas", page_icon="🗺️", layout="wide")

# Load and inject custom CSS stylesheet
css_path = os.path.join(ROOT, "style.css")
if os.path.exists(css_path):
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

API_URL = os.getenv("ATLAS_API_URL", "http://127.0.0.1:8000")


def _looks_like_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False


def render_html(html_code: str):
    st.html(html_code)


def clear_subject_caches():
    st.session_state.notes_cache = None
    st.session_state.roadmap_cache = None
    st.session_state.graph_cache = None
    st.session_state.graph_html = None
    st.session_state.graph_stats = None
    st.session_state.chat_history = []
    st.session_state.current_card = None
    st.session_state.interview_step = None
    st.session_state.interview_audio = None
    st.session_state.cross_cat_cache = None
    st.session_state.analytics_cache = None
    st.session_state.assessment = None
    st.session_state.export_pdf = None
    st.session_state.export_obsidian = None
    st.session_state.export_anki = None


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
if "active_subject" not in st.session_state:
    st.session_state.active_subject = None

AUTH_DISABLED = os.getenv("ATLAS_AUTH_DISABLED", "").lower() in ("1", "true", "yes")
GOOGLE_OAUTH_ENABLED = bool(os.getenv("ATLAS_GOOGLE_OAUTH_CLIENT_ID"))

if not AUTH_DISABLED and not st.session_state.auth_token:
    oauth_token = st.query_params.get("oauth_token")
    oauth_error = st.query_params.get("oauth_error")
    if oauth_error:
        st.error(f"Google sign-in failed: {oauth_error}")
        st.query_params.clear()
    if oauth_token:
        st.session_state.auth_token = oauth_token
        st.query_params.clear()
        st.rerun()

if not AUTH_DISABLED and not st.session_state.auth_token:
    auth_client = AtlasClient(base_url=API_URL, session_id=st.session_state.mentor_session_id)

    query = st.query_params
    default_verify = query.get("verify", "")
    default_reset = query.get("reset", "")

    # Load background image for the left panel
    bg_base64 = ""
    bg_path = os.path.join(ROOT, "assets", "left_panel_bg.png")
    if os.path.exists(bg_path):
        with open(bg_path, "rb") as f:
            bg_base64 = base64.b64encode(f.read()).decode()

    # Split screen columns
    col_left, col_right = st.columns([5, 6], gap="large")

    with col_left:
        render_html(f"""
        <div class="login-left-panel" style="background-image: url('data:image/png;base64,{bg_base64}');">
            <div class="brand-header">
                <span class="brand-icon">🗺️</span>
                <span class="brand-name">Atlas</span>
            </div>
            <div class="brand-subtitle">Your AI-powered research companion.</div>
            
            <div class="features-list">
                <div class="feature-item">
                    <div class="feature-icon-wrapper purple-bg">
                        <span class="feature-icon">📖</span>
                    </div>
                    <div class="feature-text">
                        <div class="feature-title">Create books</div>
                        <div class="feature-desc">Organize your ideas and sources in one place.</div>
                    </div>
                </div>
                <div class="feature-item">
                    <div class="feature-icon-wrapper green-bg">
                        <span class="feature-icon">🔗</span>
                    </div>
                    <div class="feature-text">
                        <div class="feature-title">Add sources</div>
                        <div class="feature-desc">Bring in content from YouTube, PDFs, images, and more.</div>
                    </div>
                </div>
                <div class="feature-item">
                    <div class="feature-icon-wrapper blue-bg">
                        <span class="feature-icon">✨</span>
                    </div>
                    <div class="feature-text">
                        <div class="feature-title">AI insights</div>
                        <div class="feature-desc">Let AI help you understand, summarize, and explore your content.</div>
                    </div>
                </div>
            </div>
        </div>
        """)

    with col_right:
        render_html("""
        <div class="login-right-header">
            <h1 class="login-title">Sign in to Atlas</h1>
            <p class="login-subtitle">Welcome back! Please sign in to continue.</p>
        </div>
        """)

        if "auth_mode" not in st.session_state:
            st.session_state.auth_mode = "Log in"

        modes = ["Log in", "Register", "Verify email", "Forgot / reset password"]
        default_index = modes.index(st.session_state.auth_mode) if st.session_state.auth_mode in modes else 0

        auth_mode = st.radio(
            "Account",
            modes,
            index=default_index,
            horizontal=True,
            label_visibility="collapsed",
            key="auth_mode_selector",
        )
        st.session_state.auth_mode = auth_mode

        if st.session_state.auth_mode == "Log in":
            email = st.text_input("Email", placeholder="Enter your email address", key="login_email")
            password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_password")

            # Checkbox and Forgot Password link styled
            c_rem, c_forgot = st.columns([1, 1])
            with c_rem:
                remember_me = st.checkbox("Remember me", value=True, key="login_remember")
            with c_forgot:
                st.markdown('<div class="forgot-link-container">', unsafe_allow_html=True)
                if st.button("Forgot your password?", key="btn_forgot_pwd", type="secondary"):
                    st.session_state.auth_mode = "Forgot / reset password"
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            if st.button("Log in", type="primary", use_container_width=True, key="btn_login_submit"):
                if email and password:
                    try:
                        st.session_state.auth_token = auth_client.login(email, password)
                        st.rerun()
                    except AtlasApiError as e:
                        st.error(str(e))
                else:
                    st.error("Please enter email and password.")

            st.markdown('<div class="login-divider"><span>or</span></div>', unsafe_allow_html=True)

            if GOOGLE_OAUTH_ENABLED:
                google_url = f"{API_URL.rstrip('/')}/auth/google/start"
                st.markdown(f"""
                <a href="{google_url}" target="_self" class="google-signin-btn">
                    <img src="https://upload.wikimedia.org/wikipedia/commons/c/c1/Google_%22G%22_logo.svg" alt="Google Logo"/>
                    Sign in with Google
                </a>
                """, unsafe_allow_html=True)

            # Footer
            st.markdown('<div class="register-footer-text">Don\'t have an account? <span class="link-span">Register</span></div>', unsafe_allow_html=True)
            if st.button("Register an account", key="btn_switch_register", type="secondary", use_container_width=True):
                st.session_state.auth_mode = "Register"
                st.rerun()

        elif st.session_state.auth_mode == "Register":
            email = st.text_input("Email", placeholder="Enter your email address", key="register_email")
            password = st.text_input("Password", type="password", placeholder="Enter your password", key="register_password")

            if st.button("Register", type="primary", use_container_width=True, key="btn_register_submit"):
                if email and password:
                    try:
                        auth_client.register(email, password)
                        st.session_state.auth_token = auth_client.login(email, password)
                        st.success("Account created — check email/console for verification token.")
                        st.rerun()
                    except AtlasApiError as e:
                        st.error(str(e))
                else:
                    st.error("Please enter email and password.")

            st.markdown('<div class="login-divider"><span>or</span></div>', unsafe_allow_html=True)

            if GOOGLE_OAUTH_ENABLED:
                google_url = f"{API_URL.rstrip('/')}/auth/google/start"
                st.markdown(f"""
                <a href="{google_url}" target="_self" class="google-signin-btn">
                    <img src="https://upload.wikimedia.org/wikipedia/commons/c/c1/Google_%22G%22_logo.svg" alt="Google Logo"/>
                    Sign in with Google
                </a>
                """, unsafe_allow_html=True)

            st.markdown('<div class="register-footer-text">Already have an account? <span class="link-span">Log in</span></div>', unsafe_allow_html=True)
            if st.button("Log in to your account", key="btn_switch_login", type="secondary", use_container_width=True):
                st.session_state.auth_mode = "Log in"
                st.rerun()

        elif st.session_state.auth_mode == "Verify email":
            email = st.text_input("Email", placeholder="Enter your email address", key="verify_email")
            verify_token = st.text_input("Verification token", value=default_verify, placeholder="Enter verification token", key="verify_token")

            if st.button("Verify email", type="primary", use_container_width=True, key="btn_verify_submit"):
                if verify_token:
                    try:
                        auth_client.verify_email(verify_token)
                        st.success("Email verified — you can log in now.")
                        st.session_state.auth_mode = "Log in"
                        st.rerun()
                    except AtlasApiError as e:
                        st.error(str(e))
                else:
                    st.error("Please enter verification token.")

            if st.button("Resend verification email", type="secondary", use_container_width=True, key="btn_resend_verify") and email:
                try:
                    auth_client.request_verify(email)
                    st.info("Verification email sent (check console if using console backend).")
                except AtlasApiError as e:
                    st.error(str(e))

            if st.button("Back to Log in", key="btn_verify_back", type="secondary", use_container_width=True):
                st.session_state.auth_mode = "Log in"
                st.rerun()

        elif st.session_state.auth_mode == "Forgot / reset password":
            email = st.text_input("Email", placeholder="Enter your email address", key="forgot_email")
            reset_token = st.text_input("Reset token (from email)", value=default_reset, placeholder="Enter reset token", key="reset_token")
            new_password = st.text_input("New password", type="password", placeholder="Enter new password", key="reset_password")

            col_forgot, col_reset = st.columns(2)
            with col_forgot:
                if st.button("Send reset email", type="secondary", use_container_width=True, key="btn_send_reset") and email:
                    try:
                        auth_client.forgot_password(email)
                        st.info("Reset email sent (check console if using console backend).")
                    except AtlasApiError as e:
                        st.error(str(e))
            with col_reset:
                if st.button("Reset password", type="primary", use_container_width=True, key="btn_reset_submit"):
                    if reset_token and new_password:
                        try:
                            auth_client.reset_password(reset_token, new_password)
                            st.success("Password updated — log in with your new password.")
                            st.session_state.auth_mode = "Log in"
                            st.rerun()
                        except AtlasApiError as e:
                            st.error(str(e))
                    else:
                         st.error("Please fill in reset token and new password.")

            if st.button("Back to Log in", key="btn_forgot_back", type="secondary", use_container_width=True):
                st.session_state.auth_mode = "Log in"
                st.rerun()


    st.stop()

api = AtlasClient(
    base_url=API_URL,
    session_id=st.session_state.mentor_session_id,
    token=st.session_state.auth_token,
)

try:
    subjects_list = api.list_subjects().get("subjects", [])
except AtlasApiError:
    subjects_list = []

subject_slugs = [s["slug"] for s in subjects_list]
if st.session_state.active_subject and st.session_state.active_subject not in subject_slugs:
    st.session_state.active_subject = None
if not subjects_list:
    st.session_state.active_subject = None

SUBJECT = st.session_state.active_subject
book_ready = SUBJECT is not None
active_display = (
    next(
        (s.get("display_name") or s["slug"] for s in subjects_list if s["slug"] == SUBJECT),
        SUBJECT,
    )
    if SUBJECT
    else None
)

st.title("🗺️ Atlas")
if active_display:
    st.caption(f"Book: **{active_display}** · API: `{API_URL}`")
elif subjects_list:
    st.caption(f"Select a book in the sidebar · API: `{API_URL}`")
else:
    st.caption(f"Create your first book in the sidebar · API: `{API_URL}`")

# Sidebar: books + ingestion
with st.sidebar:
    st.markdown('<div class="sidebar-books-header">', unsafe_allow_html=True)
    st.markdown('### 📚 Your books', unsafe_allow_html=True)
    st.markdown('<p class="sidebar-section-desc">Create and manage your books and sources.</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if subjects_list:
        for s in subjects_list:
            slug = s["slug"]
            label = s.get("display_name") or slug
            prefix = "▶ " if slug == SUBJECT else ""
            if st.button(f"{prefix}{label}", key=f"book_{slug}", use_container_width=True):
                if slug != SUBJECT:
                    st.session_state.active_subject = slug
                    clear_subject_caches()
                    st.rerun()
    else:
        st.caption("No books yet — create one below.")

    if "show_new_book" not in st.session_state:
        st.session_state.show_new_book = not subjects_list

    if st.button("📝 Create a new book", key="toggle_new_book", use_container_width=True):
        st.session_state.show_new_book = not st.session_state.show_new_book
        st.rerun()

    if st.session_state.show_new_book:
        new_subject = st.text_input("Subject name", placeholder="e.g., ml, dl, rust...", key="new_subject_name", label_visibility="collapsed")
        if st.button("+ Create book", key="create_book", type="primary", use_container_width=True):
            if new_subject.strip():
                try:
                    created = api.create_subject(new_subject.strip())
                    st.session_state.active_subject = created["slug"]
                    clear_subject_caches()
                    st.session_state.show_new_book = False
                    st.rerun()
                except AtlasApiError as e:
                    st.error(str(e))
            else:
                st.error("Please enter a subject name.")

    st.divider()
    st.markdown('<div class="sidebar-books-header">', unsafe_allow_html=True)
    st.markdown('### 📁 Add sources', unsafe_allow_html=True)
    st.markdown('<p class="sidebar-section-desc">Add content from various sources to your book.</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if not book_ready:
        if not subjects_list:
            st.caption("Create your first book above to unlock adding sources.")
        else:
            st.caption("Click a book above to enable adding sources.")

    if book_ready:
        try:
            health = api.health(SUBJECT)
            if not health.get("hindsight_ok"):
                st.error("Hindsight not configured — check `.env`")
                st.stop()
        except AtlasApiError as e:
            st.error(f"API unreachable ({e}). Start with: `uvicorn api.main:app --reload`")
            st.stop()

    # Section 1: YouTube
    st.markdown('<div class="sidebar-section-header"><span class="section-icon green">🔗</span> YouTube URL / Transcript</div>', unsafe_allow_html=True)
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        yt_url = st.text_input("YouTube URL Input", placeholder="Paste YouTube URL or transcript...", key="yt_url_sidebar", label_visibility="collapsed", disabled=not book_ready)
    with col_btn:
        add_yt = st.button("Add", key="add_youtube_btn", disabled=not book_ready)

    if add_yt and yt_url and book_ready:
        try:
            value = yt_url.strip()
            if _looks_like_url(value):
                r = api.ingest_youtube(value, SUBJECT)
            else:
                r = api.ingest_leetcode(value, SUBJECT)
            st.session_state.notes_cache = None
            st.success(f"Added {r['source']}")
            st.rerun()
        except AtlasApiError as e:
            st.error(str(e))
            if "502" in str(e) or "blocked" in str(e).lower():
                st.info(
                    "YouTube blocks cloud servers. Paste a transcript as text, "
                    "or upload a PDF/image instead."
                )

    # Section 2: PDF
    st.markdown('<div class="sidebar-section-header"><span class="section-icon purple">📁</span> Upload PDF or Word (.docx)</div>', unsafe_allow_html=True)
    doc_file = st.file_uploader(
        "Upload PDF/Word",
        type=["pdf", "docx"],
        key="doc_upload",
        disabled=not book_ready,
        label_visibility="collapsed"
    )
    if doc_file is not None:
        if st.button("Add PDF/Word", key="add_doc_btn", type="primary", use_container_width=True, disabled=not book_ready):
            try:
                with st.spinner("Uploading and indexing document…"):
                    r = api.ingest_document_upload_async(doc_file.getvalue(), doc_file.name, SUBJECT)
                st.session_state.notes_cache = None
                st.success(f"Added {r['source']}")
                st.rerun()
            except AtlasApiError as e:
                if e.status_code in (502, 503, 504):
                    st.error(
                        "Upload failed — the cloud server timed out or is waking up. "
                        "Wait a minute and try again, or use a smaller file."
                    )
                else:
                    st.error(str(e))

    # Section 3: OCR
    st.markdown('<div class="sidebar-section-header"><span class="section-icon orange">📷</span> Upload Image (OCR)</div>', unsafe_allow_html=True)
    photo_file = st.file_uploader(
        "Upload Image",
        type=["jpg", "jpeg", "png", "webp"],
        key="photo_upload",
        disabled=not book_ready,
        label_visibility="collapsed"
    )
    if photo_file is not None:
        if st.button("Add Image", key="add_photo_btn", type="primary", use_container_width=True, disabled=not book_ready):
            try:
                with st.spinner("Running OCR on image (this may take a minute)…"):
                    r = api.ingest_photo_upload_async(photo_file.getvalue(), photo_file.name, SUBJECT)
                st.session_state.notes_cache = None
                if r.get("status") == "ok":
                    st.success(f"Added {r['source']} (confidence {r['confidence']:.0%})")
                else:
                    st.warning(f"Low confidence ({r['confidence']:.0%}) — queued (# {r['queue_id']})")
                st.rerun()
            except AtlasApiError as e:
                if e.status_code in (502, 503, 504):
                    st.error(
                        "OCR failed — the cloud server timed out or is waking up. "
                        "Wait a minute and try again."
                    )
                else:
                    st.error(str(e))

    # Section 4: Paste text
    st.markdown('<div class="sidebar-section-header"><span class="section-icon blue">📝</span> Paste text</div>', unsafe_allow_html=True)
    paste_text = st.text_area("Paste text here", placeholder="Type or paste your text here...", key="paste_text_sidebar", label_visibility="collapsed", disabled=not book_ready)
    st.caption("Example: bullet points, lecture notes, questions, etc.")
    if st.button("Add Text", key="add_text_btn", type="primary", use_container_width=True, disabled=not book_ready) and paste_text:
        try:
            r = api.ingest_leetcode(paste_text, SUBJECT)
            st.session_state.notes_cache = None
            st.success(f"Added {r['source']}")
            st.rerun()
        except AtlasApiError as e:
            st.error(str(e))

    if book_ready:
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
            st.session_state.active_subject = None
            clear_subject_caches()
            st.rerun()

if not SUBJECT:
    # Render the landing page dashboard
    # 1. Header with logo and help button
    render_html(f"""
    <div class="main-header">
        <div class="dashboard-logo-container">
            <span class="dashboard-logo-icon">🗺️</span>
            <span class="dashboard-logo-text">Atlas</span>
        </div>
        <a href="https://github.com/Meg-hanaa/Atlas" target="_blank" class="help-btn">
            <span class="help-icon">❓</span> Help
        </a>
    </div>
    <div class="dashboard-api-subtitle">
        Create your first book in the sidebar or use our API: <span>{API_URL}</span>
    </div>
    """)

    # 2. Welcome card with books illustration
    illustration_base64 = ""
    ill_path = os.path.join(ROOT, "assets", "books_illustration.png")
    if os.path.exists(ill_path):
        with open(ill_path, "rb") as f:
            illustration_base64 = base64.b64encode(f.read()).decode()

    render_html(f"""
    <div class="welcome-card">
        <div class="welcome-card-content">
            <div class="welcome-card-sparkle">✨</div>
            <div class="welcome-card-title">Welcome to Atlas!</div>
            <div class="welcome-card-desc">
                Create your first book in the sidebar (e.g., ml, dl), then add sources to get started.
            </div>
        </div>
        <div class="welcome-card-image-container">
            <img src="data:image/png;base64,{illustration_base64}" class="welcome-card-image" alt="Books Illustration"/>
        </div>
    </div>
    """)

    # 3. How it works section
    render_html("""
    <div class="section-title">How it works</div>
    <div class="how-it-works-grid">
        <div class="step-card">
            <div class="step-number-badge badge-purple">1</div>
            <div class="step-icon-box">📖</div>
            <div class="step-title">Create a book</div>
            <div class="step-desc">Give your book a name to get started.</div>
        </div>
        <div class="step-arrow">&rarr;</div>
        <div class="step-card">
            <div class="step-number-badge badge-green">2</div>
            <div class="step-icon-box">🔗</div>
            <div class="step-title">Add sources</div>
            <div class="step-desc">Add content from YouTube, PDFs, images, or text.</div>
        </div>
        <div class="step-arrow">&rarr;</div>
        <div class="step-card">
            <div class="step-number-badge badge-blue">3</div>
            <div class="step-icon-box">🧠</div>
            <div class="step-title">AI processes</div>
            <div class="step-desc">Our AI will process and understand your content.</div>
        </div>
        <div class="step-arrow">&rarr;</div>
        <div class="step-card">
            <div class="step-number-badge badge-purple">4</div>
            <div class="step-icon-box">⚡</div>
            <div class="step-title">Learn & explore</div>
            <div class="step-desc">Ask questions, get insights, and master your topics.</div>
        </div>
    </div>
    """)

    # 4. Tip box
    render_html("""
    <div class="tip-banner">
        <div class="tip-icon">💡</div>
        <div class="tip-content">
            <strong>Tip:</strong> Start with a clear subject name and add diverse sources for the best results.
        </div>
    </div>
    """)

    st.stop()

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
    if "analytics_cache" not in st.session_state or st.session_state.analytics_cache is None:
        with st.spinner("Loading analytics…"):
            st.session_state.analytics_cache = api.analytics_dashboard(SUBJECT)
    dash = st.session_state.analytics_cache or {}
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
