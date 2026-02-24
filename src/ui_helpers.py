import time
import streamlit as st

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
        <summary>🐞 Errors / Bugs ({count})</summary>
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
