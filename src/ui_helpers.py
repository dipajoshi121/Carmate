import base64
import os
import time
from pathlib import Path

import streamlit as st

ROLE_USER = "user"
ROLE_BUSINESS = "business"
ROLE_ADMIN = "admin"


def get_session_role() -> str:
    u = st.session_state.get("user") or {}
    r = (u.get("role") or ROLE_USER).strip().lower()
    if r not in (ROLE_USER, ROLE_BUSINESS, ROLE_ADMIN):
        return ROLE_USER
    return r


def perform_logout():
    """Clear auth session; best-effort POST to backend when auth is not DB-only."""
    if not (os.environ.get("DATABASE_URL") or "").strip():
        try:
            import requests
            from config import CFG

            requests.post(f"{CFG.API_BASE}/api/auth/logout", timeout=10)
        except Exception:
            pass
    for k in ("token", "user", "login_intent", "register_intent"):
        st.session_state.pop(k, None)


def sync_session_role_from_db():
    """Align session role with the database so accounts stay tied to their account type."""
    if not os.environ.get("DATABASE_URL"):
        return
    uid = (st.session_state.get("user") or {}).get("id") or st.session_state.get("token")
    if not uid:
        return
    try:
        from db import get_user_by_id

        row = get_user_by_id(uid)
        if not row:
            return
        r = (row.get("role") or ROLE_USER).strip().lower()
        if r not in (ROLE_USER, ROLE_BUSINESS, ROLE_ADMIN):
            r = ROLE_USER
        u = st.session_state.get("user")
        if not isinstance(u, dict):
            u = {}
        u = {**u, "role": r}
        st.session_state["user"] = u
    except Exception:
        pass


def require_role(*allowed: str):
    if "token" not in st.session_state:
        st.warning("Please log in first.")
        if st.button("Go to Login"):
            st.switch_page("pages/login.py")
        st.stop()
    sync_session_role_from_db()
    role = get_session_role()
    allowed_l = [a.strip().lower() for a in allowed]
    if role not in allowed_l:
        st.error("You do not have access to this page.")
        if st.button("Go to Home"):
            st.switch_page("home.py")
        st.stop()


def require_any_role():
    """Any logged-in user (customer, business, or admin)."""
    if "token" not in st.session_state:
        st.warning("Please log in first.")
        if st.button("Go to Login"):
            st.switch_page("pages/login.py")
        st.stop()
    sync_session_role_from_db()

def mechanic_girl_background_css():
    res_dir = Path(__file__).resolve().parent / "pages" / "resources"
    for name in ("mechanic_girl.png", "mechanic_girl.jpg", "mechanic_girl.jpeg", "mechanic_girl.webp"):
        p = res_dir / name
        if p.exists():
            raw = p.read_bytes()
            b64 = base64.b64encode(raw).decode("ascii")
            suffix = p.suffix.lower()
            mime = "image/png" if suffix == ".png" else "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/webp"
            data_uri = f"data:{mime};base64,{b64}"
            return f"""
.stApp {{
  background: linear-gradient(180deg, rgba(255,255,255,0.75) 0%, rgba(255,255,255,0.75) 100%),
              url({data_uri}) center center no-repeat !important;
  background-size: cover !important;
  background-attachment: fixed !important;
}}
"""
    return ""

def require_login():
    if "token" not in st.session_state:
        st.warning("Please log in first.")
        if st.button("Go to Login"):
            st.switch_page("pages/login.py")
        st.stop()
    sync_session_role_from_db()

def auth_headers():
    token = st.session_state.get("token") or ""
    return {"Authorization": f"Bearer {token}"}

def log_bug(title: str, details: str = ""):
    if "error_log" not in st.session_state:
        st.session_state.error_log = []
    st.session_state.error_log.append({
        "time": time.strftime("%H:%M:%S"),
        "title": title,
        "details": details,
    })

def render_footer_bug_panel():
    if "error_log" not in st.session_state:
        st.session_state.error_log = []
    bugs = st.session_state.error_log[-5:]
    count = len(st.session_state.error_log)
    footer = """
    <div class="footer-bug-panel">
      <details {open}>
        <summary>Errors / Bugs ({count})</summary>
    """.format(open='open' if count else "", count=count)
    if count == 0:
        footer += "<div class='footer-bug-item'>No errors yet.</div>"
    else:
        for b in reversed(bugs):
            footer += """
            <div class="footer-bug-item">
              [{}] <b>{}</b><br>{}
            </div>
            """.format(b["time"], b["title"], b["details"])
    footer += "</details></div>"
    st.markdown(footer, unsafe_allow_html=True)
