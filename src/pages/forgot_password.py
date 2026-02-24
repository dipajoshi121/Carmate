import os
import re
import time
import traceback

import requests
import streamlit as st

from config import CFG
from db import create_password_reset_token

FORGOT_URL = f"{CFG.API_BASE}/api/auth/forgot-password"

def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", (email or "").strip()))

if "error_log" not in st.session_state:
    st.session_state.error_log = []

def log_bug(title: str, details: str = ""):
    st.session_state.error_log.append({
        "time": time.strftime("%H:%M:%S"),
        "title": title,
        "details": details,
    })

st.set_page_config(page_title="Carmate - Forgot Password", page_icon="🛻", layout="centered")

st.title("Forgot Password")
st.write("Enter your email address and we'll send you instructions to reset your password.")

with st.form("forgot_password_form", clear_on_submit=False):
    fp_email = st.text_input("Email for reset", key="fp_email", placeholder="e.g., arjun@example.com")
    send_btn = st.form_submit_button("Send reset link")

if send_btn:
    if not fp_email or not is_valid_email(fp_email):
        st.error("Please enter a valid email address.")
    else:
        email = fp_email.strip().lower()
        used_db = False
        if os.environ.get("DATABASE_URL"):
            token = create_password_reset_token(email)
            if token is not None:
                used_db = True
                st.success("✅ If that email exists, reset instructions were sent.")
            else:
                log_bug("Forgot password DB error", "Failed to create reset token")
        if not used_db:
            try:
                with st.spinner("Sending reset request..."):
                    response = requests.post(FORGOT_URL, json={"email": email}, timeout=10)
                if response.status_code in (200, 201, 202):
                    st.success("✅ If that email exists, reset instructions were sent.")
                else:
                    st.error(f"❌ Request failed ({response.status_code})")
                    log_bug("Forgot password API error", response.text)
            except requests.exceptions.RequestException as ex:
                st.error("❌ Could not connect to backend. Set DATABASE_URL to use the database (no backend needed for reset), or start the backend at " + CFG.API_BASE)
                log_bug("Forgot password connection error", str(ex))
            except Exception:
                st.error("❌ Unexpected error.")
                log_bug("Forgot password exception", traceback.format_exc())

st.divider()
if st.button("Back to Login"):
    st.switch_page("pages/login.py")
