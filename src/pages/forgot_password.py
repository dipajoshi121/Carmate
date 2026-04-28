import os
import re
import smtplib
import time
import traceback
from email.message import EmailMessage
from pathlib import Path

import requests
import streamlit as st

from config import CFG
from db import (
    create_password_reset_token,
    get_valid_reset_token,
    mark_reset_token_used,
    update_password_by_email,
    DatabaseError,
)
from ui_helpers import mechanic_girl_background_css

FORGOT_URL = f"{CFG.API_BASE}/api/auth/forgot-password"

def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", (email or "").strip()))


def is_valid_password(pw: str) -> str | None:
    if not pw or len(pw) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", pw):
        return "Password must include at least one letter."
    if not re.search(r"\d", pw):
        return "Password must include at least one number."
    return None


def send_reset_email(to_email: str, token: str) -> bool:
    host = (CFG.SMTP_HOST or "").strip()
    user = (CFG.SMTP_USERNAME or "").strip()
    pw = CFG.SMTP_PASSWORD or ""
    from_email = (CFG.SMTP_FROM_EMAIL or user).strip()
    if not (host and from_email):
        return False
    msg = EmailMessage()
    msg["Subject"] = "Carmate password reset code"
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(
        "Use this reset code to update your Carmate password:\n\n"
        f"{token}\n\n"
        "If you did not request this change, ignore this email."
    )
    server = None
    try:
        server = smtplib.SMTP(host, CFG.SMTP_PORT, timeout=15)
        if CFG.SMTP_USE_TLS:
            server.starttls()
        if user and pw:
            server.login(user, pw)
        server.send_message(msg)
        return True
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass

if "error_log" not in st.session_state:
    st.session_state.error_log = []

def log_bug(title: str, details: str = ""):
    st.session_state.error_log.append({
        "time": time.strftime("%H:%M:%S"),
        "title": title,
        "details": details,
    })

st.set_page_config(page_title="Carmate - Forgot Password", page_icon="", layout="centered")

BASE_DIR = Path(__file__).resolve().parent
CSS_PATH = BASE_DIR / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
bg = mechanic_girl_background_css()
if bg:
    st.markdown(f"<style>{bg}</style>", unsafe_allow_html=True)

st.title("Forgot Password")
st.write("Request a reset code by email, then verify it to set a new password.")

tab_req, tab_reset = st.tabs(["1) Send reset code", "2) Verify code & reset"])

with tab_req:
    with st.form("forgot_password_form", clear_on_submit=False):
        fp_email = st.text_input("Email for reset", key="fp_email", placeholder="e.g., arjun@example.com")
        send_btn = st.form_submit_button("Send reset code")

    if send_btn:
        if not fp_email or not is_valid_email(fp_email):
            st.error("Please enter a valid email address.")
        else:
            email = fp_email.strip().lower()
            used_db = False
            if os.environ.get("DATABASE_URL"):
                try:
                    token = create_password_reset_token(email)
                    if token is not None:
                        used_db = True
                        if send_reset_email(email, token):
                            st.success("If that email exists, a reset code was sent.")
                        else:
                            st.error("Email sending is not configured. Set SMTP_* settings in .env.")
                            st.info("SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL")
                            log_bug("Forgot password email", "SMTP not configured or send failed")
                    else:
                        log_bug("Forgot password DB error", "Failed to create reset token")
                except DatabaseError as e:
                    used_db = True
                    st.error("Database error: " + str(e))
                    st.info("Check DATABASE_URL and run: python run_migration.py")
                    log_bug("Forgot password DB error", str(e))
                except smtplib.SMTPAuthenticationError:
                    used_db = True
                    st.error("SMTP authentication failed. Use a Gmail App Password in SMTP_PASSWORD.")
                    st.info("Google account must have 2-Step Verification enabled.")
                    log_bug("Forgot password SMTP auth", "SMTPAuthenticationError")
                except Exception:
                    used_db = True
                    st.error("Could not send reset email.")
                    log_bug("Forgot password email exception", traceback.format_exc())
            if not used_db:
                try:
                    with st.spinner("Sending reset request..."):
                        response = requests.post(FORGOT_URL, json={"email": email}, timeout=10)
                    if response.status_code in (200, 201, 202):
                        st.success("If that email exists, reset instructions were sent.")
                    else:
                        st.error(f"Request failed ({response.status_code})")
                        log_bug("Forgot password API error", response.text)
                except requests.exceptions.RequestException as ex:
                    st.error("Could not connect to backend. Set DATABASE_URL to use the database (no backend needed for reset), or start the backend at " + CFG.API_BASE)
                    log_bug("Forgot password connection error", str(ex))
                except Exception:
                    st.error("Unexpected error.")
                    log_bug("Forgot password exception", traceback.format_exc())

with tab_reset:
    with st.form("reset_password_form", clear_on_submit=False):
        rp_email = st.text_input("Email", key="rp_email", placeholder="e.g., arjun@example.com")
        reset_code = st.text_input("Reset code from email", key="rp_code")
        new_password = st.text_input("New password", key="rp_new_pw", type="password")
        confirm_password = st.text_input("Confirm new password", key="rp_confirm_pw", type="password")
        reset_btn = st.form_submit_button("Reset password")

    if reset_btn:
        email = (rp_email or "").strip().lower()
        code = (reset_code or "").strip()
        errors = []
        if not is_valid_email(email):
            errors.append("Please enter a valid email address.")
        if not code:
            errors.append("Reset code is required.")
        pw_err = is_valid_password(new_password)
        if pw_err:
            errors.append(pw_err)
        if new_password != confirm_password:
            errors.append("Passwords do not match.")
        if errors:
            st.error(" | ".join(errors))
        elif not os.environ.get("DATABASE_URL"):
            st.error("Password reset verification requires DATABASE_URL.")
        else:
            try:
                row = get_valid_reset_token(code)
                if not row or (row.get("email") or "").strip().lower() != email:
                    st.error("Invalid or expired reset code.")
                elif not update_password_by_email(email, new_password):
                    st.error("Could not update password. Please try again.")
                else:
                    mark_reset_token_used(code)
                    st.success("Password reset successful. You can now log in.")
            except DatabaseError as e:
                st.error("Database error: " + str(e))
                log_bug("Reset password DB error", str(e))
            except Exception:
                st.error("Unexpected error.")
                log_bug("Reset password exception", traceback.format_exc())

st.divider()
if st.button("Back to Login"):
    st.switch_page("pages/login.py")
