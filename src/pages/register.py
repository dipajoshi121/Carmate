import os
import re
import sys
import time
import traceback
from pathlib import Path

import requests
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from config import CFG
from db import create_user, user_exists_by_email, DatabaseError
from ui_helpers import mechanic_girl_background_css

REGISTER_URL = f"{CFG.API_BASE}/api/auth/register"

st.set_page_config(page_title="Carmate - Register", page_icon="", layout="centered")

CSS_PATH = BASE_DIR / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
bg = mechanic_girl_background_css()
if bg:
    st.markdown(f"<style>{bg}</style>", unsafe_allow_html=True)

LOGO_PATH = BASE_DIR / "resources" / "logo.png"
if LOGO_PATH.exists():
    st.image(str(LOGO_PATH), width=150)

if "error_log" not in st.session_state:
    st.session_state.error_log = []

def log_bug(title: str, details: str = ""):
    st.session_state.error_log.append({
        "time": time.strftime("%H:%M:%S"),
        "title": title,
        "details": details,
    })

def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", (email or "").strip()))

st.title("Register")
st.write("Create an account to access Carmate services.")

with st.form("register_form", clear_on_submit=False):
    full_name = st.text_input("Full name", placeholder="e.g., Arjun Khatri")
    email = st.text_input("Email", placeholder="e.g., arjun@example.com")
    password = st.text_input("Password", type="password", placeholder="Choose a password")
    confirm_password = st.text_input("Confirm password", type="password", placeholder="Confirm your password")
    submitted = st.form_submit_button("Register")

if submitted:
    errors = []
    if not full_name or len(full_name.strip()) < 2:
        errors.append("Full name is required (at least 2 characters).")
    if not is_valid_email(email):
        errors.append("Please enter a valid email address.")
    if not password or len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if password and not re.search(r"[A-Za-z]", password):
        errors.append("Password must include at least one letter.")
    if password and not re.search(r"\d", password):
        errors.append("Password must include at least one number.")
    if password != confirm_password:
        errors.append("Passwords do not match.")

    if errors:
        st.error(" | ".join(errors))
        log_bug("Register form validation", " | ".join(errors))
    else:
        email_clean = email.strip().lower()
        full_name_clean = full_name.strip()
        used_db = False
        if os.environ.get("DATABASE_URL"):
            try:
                if user_exists_by_email(email_clean):
                    st.error("An account with this email already exists.")
                    log_bug("Register (duplicate)", email_clean)
                    used_db = True
                else:
                    user = create_user(email_clean, password, full_name_clean, phone=None)
                    if user:
                        used_db = True
                        st.success("Account created. You can now log in.")
                        st.session_state["token"] = str(user.get("id", ""))
                        st.session_state["user"] = {
                            "id": str(user.get("id")),
                            "email": user.get("email"),
                            "fullName": user.get("full_name"),
                            "phone": user.get("phone"),
                            "isActive": user.get("is_active"),
                        }
                        if st.button("Go to Login"):
                            st.switch_page("pages/login.py")
                    else:
                        st.error("Could not create account. Please try again.")
                        log_bug("Register DB error", "create_user returned None")
                        used_db = True
            except DatabaseError as e:
                used_db = True
                st.error("Database error: " + str(e))
                st.info("Check DATABASE_URL and run: python run_migration.py")
                log_bug("Register DB error", str(e))
        if not used_db:
            try:
                with st.spinner("Creating account..."):
                    resp = requests.post(
                        REGISTER_URL,
                        json={"fullName": full_name_clean, "email": email_clean, "password": password},
                        timeout=10,
                    )
                if resp.status_code in (200, 201):
                    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    st.success("Account created. You can now log in.")
                    if "token" in data:
                        st.session_state["token"] = data["token"]
                    if "user" in data:
                        st.session_state["user"] = data["user"]
                    if st.button("Go to Login"):
                        st.switch_page("pages/login.py")
                elif resp.status_code == 400:
                    try:
                        msg = resp.json().get("message", "Bad Request")
                    except Exception:
                        msg = resp.text
                    st.error(msg)
                    log_bug("Register (400)", msg)
                elif resp.status_code == 409:
                    st.error("An account with this email already exists.")
                    log_bug("Register (409)", resp.text)
                elif resp.status_code == 403:
                    st.error("Access denied (403). Set DATABASE_URL to use the database, or ensure the backend is running at " + CFG.API_BASE)
                    log_bug("Register 403", resp.text)
                else:
                    st.error(f"Server error ({resp.status_code}). Ensure the backend is running at {CFG.API_BASE}.")
                    log_bug(f"Register server error {resp.status_code}", resp.text)
            except requests.exceptions.RequestException as ex:
                st.error("Could not connect to backend. Set DATABASE_URL to use the database (no backend needed for register), or start the backend at " + CFG.API_BASE)
                log_bug("Register connection error", str(ex))
            except Exception:
                st.error("Unexpected error.")
                log_bug("Register exception", traceback.format_exc())

st.divider()
if st.button("Already have an account? Log in"):
    st.switch_page("pages/login.py")
