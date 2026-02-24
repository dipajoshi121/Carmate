import os
import re
import time
import traceback
from pathlib import Path

import requests
import streamlit as st

from config import CFG
from db import verify_password

LOGIN_URL = f"{CFG.API_BASE}/api/auth/login"
FORGOT_URL = f"{CFG.API_BASE}/api/auth/forgot-password"

st.set_page_config(page_title="Carmate - Login", page_icon="🛻", layout="centered")

BASE_DIR = Path(__file__).resolve().parent

if BASE_DIR.name == "pages":
    PROJECT_ROOT = BASE_DIR.parent.parent
else:
    PROJECT_ROOT = BASE_DIR.parent

RES_DIR = PROJECT_ROOT / "resources"
LOGO_PATH = RES_DIR / "logo.png"
CSS_PATH = RES_DIR / "carmate.css"

if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

if "error_log" not in st.session_state:
    st.session_state.error_log = []

def log_bug(title: str, details: str = ""):
    st.session_state.error_log.append({
        "time": time.strftime("%H:%M:%S"),
        "title": title,
        "details": details
    })

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "resources" / "logo.png"
if LOGO_PATH.exists():
    st.image(str(LOGO_PATH), width=150)
else:
    st.warning(f"Logo not found at: {LOGO_PATH}")
    log_bug("Logo missing", str(LOGO_PATH))

def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", (email or "").strip()))

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
        email_clean = email.strip().lower()
        used_db = False
        if os.environ.get("DATABASE_URL"):
            user = verify_password(email_clean, password)
            if user:
                used_db = True
                st.success("✅ Login successful!")
                st.session_state["token"] = str(user.get("id", ""))
                st.session_state["user"] = {
                    "id": str(user.get("id")),
                    "email": user.get("email"),
                    "fullName": user.get("full_name"),
                    "phone": user.get("phone"),
                    "isActive": user.get("is_active"),
                }
            else:
                st.error("❌ Invalid email or password.")
                log_bug("Login failed (auth)", "Invalid credentials")
        if not used_db:
            try:
                with st.spinner("Logging in..."):
                    resp = requests.post(LOGIN_URL, json={"email": email_clean, "password": password}, timeout=10)
                if resp.status_code in (200, 201):
                    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    st.success("✅ Login successful!")
                    if "token" in data:
                        st.session_state["token"] = data["token"]
                    if "user" in data:
                        st.session_state["user"] = data["user"]
                elif resp.status_code == 401:
                    st.error("❌ Invalid email or password.")
                    log_bug("Login failed (auth)", resp.text)
                elif resp.status_code == 403:
                    st.error("❌ Access denied (403). If using the database, set DATABASE_URL. Otherwise ensure the backend is running at " + CFG.API_BASE)
                    log_bug("Login 403", resp.text)
                elif resp.status_code == 400:
                    try:
                        backend_msg = resp.json().get("message", "Bad Request")
                    except Exception:
                        backend_msg = resp.text
                    st.error(f"❌ {backend_msg}")
                    log_bug("Login failed (400)", backend_msg)
                else:
                    st.error(f"❌ Server error ({resp.status_code}). Ensure the backend is running at {CFG.API_BASE}.")
                    log_bug(f"Login server error {resp.status_code}", resp.text)
            except requests.exceptions.RequestException as ex:
                st.error("❌ Could not connect to backend. Set DATABASE_URL in your environment to use the database (no backend needed for login), or start the backend at " + CFG.API_BASE)
                log_bug("Backend connection error", str(ex))
            except Exception:
                st.error("❌ Unexpected error.")
                log_bug("Frontend exception", traceback.format_exc())

st.divider()

col_a, col_b = st.columns(2)

with col_a:
    if st.button("Create a new account (Register)"):
        st.switch_page("pages/register.py")

with col_b:
    if st.button("Forgot Password?"):
        st.switch_page("pages/forgot_password.py")
