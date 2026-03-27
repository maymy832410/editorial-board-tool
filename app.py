"""Editorial Board Invitation Tool — Streamlit multipage entry point."""

import streamlit as st

st.set_page_config(
    page_title="Editorial Board Tool",
    page_icon="📬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Shared session state init ──
if "authors" not in st.session_state:
    st.session_state.authors = []
if "search_done" not in st.session_state:
    st.session_state.search_done = False
if "retraction_checker" not in st.session_state:
    st.session_state.retraction_checker = None
if "db_ready" not in st.session_state:
    st.session_state.db_ready = False

# ── DB init (once per session) ──
if not st.session_state.db_ready:
    try:
        from db_client import init_db, check_connection
        if check_connection():
            init_db()
            st.session_state.db_ready = True
    except Exception:
        pass  # DB may not be configured in local dev

# ── Home page ──
st.title("📬 Editorial Board Invitation Tool")

st.markdown("""
Welcome! This tool helps you find researchers and invite them to join your journal's editorial board.

### Workflow
1. **🔍 Search** — Configure filters and search OpenAlex for researchers
2. **📋 Results** — Review results, fetch emails, check retractions
3. **📬 Send Invitations** — Configure journal details and send invitations
4. **📊 History** — View sent log, import bounces, upload retraction data

### Getting Started
Use the sidebar to navigate between pages.
""")

if st.session_state.db_ready:
    st.success("✅ Database connected")
else:
    st.warning("⚠️ Database not connected. Set DATABASE_URL environment variable for full functionality.")

# Show quick stats if DB is available
if st.session_state.db_ready:
    try:
        from db_client import get_sent_count, get_all_bounced
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Invitations Sent", get_sent_count())
        with col2:
            st.metric("Bounced Emails", len(get_all_bounced()))
    except Exception:
        pass
