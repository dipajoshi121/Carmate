import base64
import time
from pathlib import Path

import streamlit as st

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
