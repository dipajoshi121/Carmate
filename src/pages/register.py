import re
import time
import traceback
from pathlib import Path

import requests
import streamlit as st

# ------------------ API (BACKEND) ------------------
API_BASE = "http://localhost:8501"
LOGIN_URL = f"{API_BASE}/api/auth/login"
FORGOT_URL = f"{API_BASE}/api/auth/forgot-password"

# ------------------ PAGE ------------------
st.set_page_config(page_title="Carmate - Login", page_icon="🛻", layout="centered")

# ------------------ PATHS (WORKS from src/ and src/pages/) ------------------
BASE_DIR = Path(__file__).resolve().parent

if BASE_DIR.name == "pages":
    PROJECT_ROOT = BASE_DIR.parent.parent   # .../Carmate
else:
    PROJECT_ROOT = BASE_DIR.parent          # .../Carmate

RES_DIR = PROJECT_ROOT / "resources"
LOGO_PATH = RES_DIR / "logo.png"
CSS_PATH = RES_DIR / "carmate.css"

# ------------------ LOAD CSS (optional) ------------------
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

# ------------------ SIMPLE ERROR LOG (footer panel uses this) ------------------
if "error_log" not in st.session_state:
    st.session_state.error_log = []

def log_bug(title: str, details: str = ""):
    st.session_state.error_log.append({
        "time": time.strftime("%H:%M:%S"),
        "title": title,
        "details": details
    })

# ------------------ LOGO (NOT CLICKABLE) ------------------
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "resources" / "logo.png"
if LOGO_PATH.exists():
    st.image(str(LOGO_PATH), width=150)
else:
    st.warning(f"Logo not found at: {LOGO_PATH}")
    log_bug("Logo missing", str(LOGO_PATH))

# ------------------ VALIDATORS ------------------
def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", (email or "").strip()))

# ------------------ UI ------------------
st.title("Login")
st.write("Sign in to access Carmate services.")

with st.form("login_form", clear_on_submit=False):
    email = st.text_input("Email", placeholder="e.g., arjun@example.com")
    password = st.text_input("Password", type="password", placeholder="Enter your password")
    submitted = st.form_submit_button("Login")

if submitted:
    errors = []
    if not is_valid_email(email):
        errors.append("Please enter a valid email address.")
    if not password:
        errors.append("Password is required.")

    if errors:
        st.error(" | ".join(errors))
        log_bug("Login form validation", " | ".join(errors))
    else:
        payload = {"email": email.strip().lower(), "password": password}
        try:
            with st.spinner("Logging in..."):
                resp = requests.post(LOGIN_URL, json=payload, timeout=10)

            if resp.status_code in (200, 201):
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                st.success("✅ Login successful!")
                if "token" in data:
                    st.session_state["token"] = data["token"]
                if "user" in data:
                    st.session_state["user"] = data["user"]

            elif resp.status_code in (401, 403):
                st.error("❌ Invalid email or password.")
                log_bug("Login failed (auth)", resp.text)

            elif resp.status_code == 400:
                try:
                    backend_msg = resp.json().get("message", "Bad Request")
                except Exception:
                    backend_msg = resp.text
                st.error(f"❌ {backend_msg}")
                log_bug("Login failed (400)", backend_msg)

            else:
                st.error(f"❌ Server error ({resp.status_code})")
                log_bug(f"Login server error {resp.status_code}", resp.text)

        except requests.exceptions.RequestException as ex:
            st.error("❌ Could not connect to backend API.")
            log_bug("Backend connection error", str(ex))
        except Exception:
            st.error("❌ Unexpected error.")
            log_bug("Frontend exception", traceback.format_exc())

# ------------------ REGISTER + FORGOT PASSWORD ------------------
st.divider()

col_a, col_b = st.columns(2)

# Button to switch to the Register page
with col_a:
    if st.button("Create a new account (Register)"):
        st.switch_page("register")  # Switch to register page (no ".py" extension)

with col_b:
    with st.popover("Forgot Password?"):
        st.write("Enter your email and we’ll send reset instructions (if your backend supports it).")
        fp_email = st.text_input("Email for reset", key="fp_email", placeholder="e.g., arjun@example.com")
        send_btn = st.button("Send reset link", key="fp_send")

        if send_btn:
            if not is_valid_email(fp_email):
                st.error("Please enter a valid email.")
                log_bug("Forgot password validation", fp_email)
            else:
                try:
                    with st.spinner("Sending reset request..."):
                        r = requests.post(FORGOT_URL, json={"email": fp_email.strip().lower()}, timeout=10)

                    if r.status_code in (200, 201, 202):
                        st.success("✅ If that email exists, reset instructions were sent.")
                    else:
                        st.error(f"❌ Request failed ({r.status_code})")
                        log_bug("Forgot password API error", r.text)

                except requests.exceptions.RequestException as ex:
                    st.error("❌ Could not connect to backend API.")
                    log_bug("Forgot password connection error", str(ex))
                except Exception:
                    st.error("❌ Unexpected error.")
                    log_bug("Forgot password exception", traceback.format_exc())

# ------------------ FOOTER BUG PANEL ------------------
st.markdown("""
<style>
.footer-bug-panel {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    background: #020617;
    color: #ffffff;
    padding: 8px 14px;
    font-size: 12px;
    border-top: 1px solid #334155;
    z-index: 9999;
}
.footer-bug-panel summary {
    cursor: pointer;
    font-weight: 600;
}
.footer-bug-item {
    margin-top: 6px;
    border-top: 1px dashed #475569;
    padding-top: 4px;
    white-space: pre-wrap;
}
</style>
""", unsafe_allow_html=True)

bugs = st.session_state.error_log[-5:]
count = len(st.session_state.error_log)

footer = f"""
<div class="footer-bug-panel">
  <details {"open" if count else ""}>
    <summary>🐞 Errors / Bugs ({count})</summary>
"""

if count == 0:
    footer += "<div class='footer-bug-item'>No errors yet.</div>"
else:
    for b in reversed(bugs):
        footer += f"""
        <div class="footer-bug-item">
          [{b['time']}] <b>{b['title']}</b><br>
          {b['details']}
        </div>
        """

footer += "</details></div>"

st.markdown(footer, unsafe_allow_html=True)
