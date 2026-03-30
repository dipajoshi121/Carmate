import os
import re
import time
import traceback
from pathlib import Path

import requests
import streamlit as st

from config import CFG
from db import verify_password, DatabaseError
from ui_helpers import mechanic_girl_background_css, ROLE_USER, ROLE_BUSINESS, ROLE_ADMIN

LOGIN_URL = f"{CFG.API_BASE}/api/auth/login"
FORGOT_URL = f"{CFG.API_BASE}/api/auth/forgot-password"

st.set_page_config(page_title="Carmate - Login", page_icon="", layout="centered")

BASE_DIR = Path(__file__).resolve().parent
RES_DIR = BASE_DIR / "resources"
LOGO_PATH = RES_DIR / "logo.png"
CSS_PATH = RES_DIR / "carmate.css"

if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
bg = mechanic_girl_background_css()
if bg:
    st.markdown(f"<style>{bg}</style>", unsafe_allow_html=True)

if "error_log" not in st.session_state:
    st.session_state.error_log = []

def log_bug(title: str, details: str = ""):
    st.session_state.error_log.append({
        "time": time.strftime("%H:%M:%S"),
        "title": title,
        "details": details
    })

if LOGO_PATH.exists():
    st.image(str(LOGO_PATH), width=150)
else:
    st.warning(f"Logo not found at: {LOGO_PATH}")
    log_bug("Logo missing", str(LOGO_PATH))

def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", (email or "").strip()))

intent = (st.session_state.get("login_intent") or ROLE_USER).strip().lower()
if intent not in (ROLE_USER, ROLE_BUSINESS, ROLE_ADMIN):
    intent = ROLE_USER

titles = {
    ROLE_USER: "Customer sign-in",
    ROLE_BUSINESS: "Business sign-in",
    ROLE_ADMIN: "Admin sign-in",
}
st.title(titles.get(intent, "Sign in"))
st.write("Sign in with the account type you selected on the home page.")
if intent == ROLE_USER:
    st.caption("Customer accounts can only sign in here—not as business or admin.")
elif intent == ROLE_BUSINESS:
    st.caption("Business accounts (shop owner) can only sign in here—not as customer or admin.")
else:
    st.caption("Administrator accounts can only sign in here. Admins can manage customers and businesses from the admin dashboard.")

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
            try:
                user = verify_password(email_clean, password)
                if user:
                    used_db = True
                    acc_role = (user.get("role") or ROLE_USER).strip().lower()
                    if acc_role not in (ROLE_USER, ROLE_BUSINESS, ROLE_ADMIN):
                        acc_role = ROLE_USER
                    if intent == ROLE_USER and acc_role != ROLE_USER:
                        st.error(
                            "This email is not a customer account. Customer accounts can only use **Customer login**. "
                            "Use **Business login** or **Admin login** on the home page if you registered as a shop or admin."
                        )
                    elif intent == ROLE_BUSINESS and acc_role != ROLE_BUSINESS:
                        st.error(
                            "This email is not a business account. Business accounts can only use **Business login**. "
                            "Use **Customer login** for personal accounts or **Admin login** for administrators."
                        )
                    elif intent == ROLE_ADMIN and acc_role != ROLE_ADMIN:
                        st.error(
                            "This email is not an administrator. Admin accounts can only use **Admin login**."
                        )
                    else:
                        st.session_state["token"] = str(user.get("id", ""))
                        st.session_state["user"] = {
                            "id": str(user.get("id")),
                            "email": user.get("email"),
                            "fullName": user.get("full_name"),
                            "phone": user.get("phone"),
                            "isActive": user.get("is_active"),
                            "role": acc_role,
                        }
                        st.session_state.pop("login_intent", None)
                        if acc_role == ROLE_USER:
                            st.switch_page("pages/my_request.py")
                        elif acc_role == ROLE_BUSINESS:
                            st.switch_page("pages/business_dashboard.py")
                        else:
                            st.switch_page("pages/admin_dashboard.py")
                else:
                    st.error("Invalid email or password.")
                    log_bug("Login failed (auth)", "Invalid credentials")
            except DatabaseError as e:
                used_db = True
                st.error("Database error: " + str(e))
                st.info("Check DATABASE_URL and run: python run_migration.py")
                log_bug("Login DB error", str(e))
        if not used_db:
            try:
                with st.spinner("Logging in..."):
                    resp = requests.post(LOGIN_URL, json={"email": email_clean, "password": password}, timeout=10)
                if resp.status_code in (200, 201):
                    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    if "token" in data:
                        st.session_state["token"] = data["token"]
                    if "user" in data:
                        u = data["user"]
                        if isinstance(u, dict) and "role" not in u:
                            u = {**u, "role": ROLE_USER}
                        acc_role = (u.get("role") or ROLE_USER).strip().lower()
                        if acc_role not in (ROLE_USER, ROLE_BUSINESS, ROLE_ADMIN):
                            acc_role = ROLE_USER
                        u = {**u, "role": acc_role}
                        if intent == ROLE_USER and acc_role != ROLE_USER:
                            st.error(
                                "This email is not a customer account. Customer accounts can only use **Customer login**. "
                                "Use **Business login** or **Admin login** on the home page if you registered as a shop or admin."
                            )
                        elif intent == ROLE_BUSINESS and acc_role != ROLE_BUSINESS:
                            st.error(
                                "This email is not a business account. Business accounts can only use **Business login**. "
                                "Use **Customer login** for personal accounts or **Admin login** for administrators."
                            )
                        elif intent == ROLE_ADMIN and acc_role != ROLE_ADMIN:
                            st.error(
                                "This email is not an administrator. Admin accounts can only use **Admin login**."
                            )
                        else:
                            st.session_state["user"] = u
                            st.session_state.pop("login_intent", None)
                            if acc_role == ROLE_BUSINESS:
                                st.switch_page("pages/business_dashboard.py")
                            elif acc_role == ROLE_ADMIN:
                                st.switch_page("pages/admin_dashboard.py")
                            else:
                                st.switch_page("pages/my_request.py")
                    elif intent == ROLE_USER:
                        st.session_state.pop("login_intent", None)
                        st.switch_page("pages/my_request.py")
                    else:
                        st.error("Server did not return a user profile. Use DATABASE_URL for business or admin login, or update the backend.")
                elif resp.status_code == 401:
                    st.error("Invalid email or password.")
                    log_bug("Login failed (auth)", resp.text)
                elif resp.status_code == 403:
                    st.error("Access denied (403). If using the database, set DATABASE_URL. Otherwise ensure the backend is running at " + CFG.API_BASE)
                    log_bug("Login 403", resp.text)
                elif resp.status_code == 400:
                    try:
                        backend_msg = resp.json().get("message", "Bad Request")
                    except Exception:
                        backend_msg = resp.text
                    st.error(backend_msg)
                    log_bug("Login failed (400)", backend_msg)
                else:
                    st.error(f"Server error ({resp.status_code}). Ensure the backend is running at {CFG.API_BASE}.")
                    log_bug(f"Login server error {resp.status_code}", resp.text)
            except requests.exceptions.RequestException as ex:
                st.error("Could not connect to backend. Set DATABASE_URL in your environment to use the database (no backend needed for login), or start the backend at " + CFG.API_BASE)
                log_bug("Backend connection error", str(ex))
            except Exception:
                st.error("Unexpected error.")
                log_bug("Frontend exception", traceback.format_exc())

st.divider()

col_a, col_b = st.columns(2)

with col_a:
    if st.button("Create a new account (Register)"):
        st.switch_page("pages/register.py")

with col_b:
    if st.button("Forgot Password?"):
        st.switch_page("pages/forgot_password.py")
