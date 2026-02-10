import re
import time
import traceback
import base64
from pathlib import Path

import requests
import streamlit as st


# ------------------ API ------------------
API_BASE = "http://localhost:8501"
REGISTER_URL = f"{API_BASE}/api/auth/register"


# ------------------ PAGE ------------------
st.set_page_config(page_title="Carmate - Register", page_icon="🛻", layout="centered")


# ------------------ PATHS ------------------
BASE_DIR = Path(__file__).resolve().parent          # .../Carmate/src
RES_DIR = BASE_DIR.parent / "resources"            # .../Carmate/resources
LOGO_PATH = RES_DIR / "logo.png"
CSS_PATH = RES_DIR / "carmate.css"


# ------------------ LOAD CSS ------------------
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
else:
    st.warning(f"CSS not found at: {CSS_PATH}")


# ------------------ SESSION BUG STORE ------------------
if "error_log" not in st.session_state:
    st.session_state.error_log = []


def log_bug(title: str, details: str = ""):
    st.session_state.error_log.append({
        "time": time.strftime("%H:%M:%S"),
        "title": title,
        "details": details
    })


# ------------------ LOGO AS IMAGE BUTTON (ONLY PHOTO) ------------------
# IMPORTANT: This MUST be the first st.button on the page for the CSS selector to work.
if LOGO_PATH.exists():
    logo_b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8")

    # Inject background-image (kept here because CSS file can't embed dynamic base64)
    st.markdown(
        f"""
        <style>
        div[data-testid="stButton"]:first-of-type > button {{
          background-image: url("data:image/png;base64,{logo_b64}") !important;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

    if st.button(" ", key="logo_btn"):
        st.switch_page("login.py")
else:
    st.warning(f"Logo not found at: {LOGO_PATH}")


# ------------------ Validators ------------------
def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", (email or "").strip()))


def is_valid_phone(phone: str) -> bool:
    digits = re.sub(r"[^\d]", "", phone or "")
    return 7 <= len(digits) <= 15


def password_policy(password: str):
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", password):
        return False, "Password must include at least one letter."
    if not re.search(r"\d", password):
        return False, "Password must include at least one number."
    return True, ""


# ------------------ UI ------------------
st.title("User Account Registration")
st.write("Create an account to access Carmate services.")

with st.form("register_form", clear_on_submit=False):
    full_name = st.text_input("Full Name", placeholder="e.g., Arjun Khatri")
    email = st.text_input("Email", placeholder="e.g., arjun@example.com")
    phone = st.text_input("Phone Number", placeholder="e.g., +1 555-555-5555")
    password = st.text_input("Password", type="password", placeholder="Min 8 chars, letters + numbers")
    confirm_password = st.text_input("Confirm Password", type="password")
    role = st.selectbox("Role", ["customer", "provider"], index=0)

    submitted = st.form_submit_button("Create Account")


if submitted:
    errors = []

    if not full_name or len(full_name.strip()) < 2:
        errors.append("Full name is required.")
    if not is_valid_email(email):
        errors.append("Invalid email address.")
    if not is_valid_phone(phone):
        errors.append("Invalid phone number.")

    ok, msg = password_policy(password)
    if not ok:
        errors.append(msg)

    if password != confirm_password:
        errors.append("Passwords do not match.")

    if errors:
        st.error(" | ".join(errors))
        log_bug("Form validation error", " | ".join(errors))

    else:
        payload = {
            "fullName": full_name.strip(),
            "email": email.strip().lower(),
            "phone": phone.strip(),
            "password": password,
            "role": role
        }

        try:
            with st.spinner("Creating your account..."):
                resp = requests.post(REGISTER_URL, json=payload, timeout=10)

            if resp.status_code == 201:
                st.success("✅ Registration successful!")

            elif resp.status_code == 409:
                st.warning("⚠️ Email already registered.")
                log_bug("Duplicate email (409)", resp.text)

            elif resp.status_code == 400:
                try:
                    backend_msg = resp.json().get("message", "Bad Request")
                except Exception:
                    backend_msg = resp.text
                st.error(f"❌ Validation error: {backend_msg}")
                log_bug("Backend validation error (400)", backend_msg)

            else:
                st.error(f"❌ Server error ({resp.status_code})")
                log_bug(f"Unexpected status {resp.status_code}", resp.text)

        except requests.exceptions.RequestException as ex:
            st.error("❌ Backend connection failed.")
            log_bug("Backend connection error", str(ex))

        except Exception:
            st.error("❌ Unexpected frontend error.")
            log_bug("Frontend exception", traceback.format_exc())


# ------------------ FOOTER BUG PANEL ------------------
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
