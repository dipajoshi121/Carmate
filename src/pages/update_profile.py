import os
import re
import traceback
from pathlib import Path

import requests
import streamlit as st

from config import CFG

UPDATE_PROFILE_URL = f"{CFG.API_BASE}/api/auth/updateProfile"
LOGOUT_URL = f"{CFG.API_BASE}/api/auth/logout"

st.set_page_config(page_title="Carmate - Update Profile", page_icon="🛻", layout="centered")

BASE_DIR = Path(__file__).resolve().parent
CSS_PATH = BASE_DIR / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
else:
    st.warning(f"CSS file not found at: {CSS_PATH}")

st.title("Update Your Profile")
st.write("Update your profile information below.")

user_data = {
    "fullName": "Arjun Khatri",
    "email": "arjun@example.com",
    "phone": "+1 555-555-5555",
}

if st.button("Logout"):
    try:
        resp = requests.post(LOGOUT_URL)
        if resp.status_code == 200:
            st.success(" Logged out successfully!")
            if "token" in st.session_state:
                del st.session_state["token"]
            if "user" in st.session_state:
                del st.session_state["user"]
            st.switch_page("pages/login.py")
        else:
            st.error(" Logout failed. Please try again.")
    except requests.exceptions.RequestException as ex:
        st.error(" Could not connect to backend. Set DATABASE_URL or start the backend at " + CFG.API_BASE)

with st.form("update_profile_form", clear_on_submit=False):
    full_name = st.text_input("Full Name", placeholder="e.g., Arjun Khatri", value=user_data["fullName"])
    email = st.text_input("Email", placeholder="e.g., arjun@example.com", value=user_data["email"])
    phone = st.text_input("Phone Number", placeholder="e.g., +1 555-555-5555", value=user_data["phone"])
    password = st.text_input("Password", type="password", placeholder="Leave blank if unchanged")
    confirm_password = st.text_input("Confirm Password", type="password", placeholder="Leave blank if unchanged")

    submit_button = st.form_submit_button("Update Profile")

if submit_button:
    errors = []

    if not full_name or len(full_name.strip()) < 2:
        errors.append("Full name is required (at least 2 characters).")
    
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        errors.append("Please enter a valid email address.")
    
    digits = re.sub(r"[^\d]", "", phone or "")
    if not (7 <= len(digits) <= 15):
        errors.append("Please enter a valid phone number (7–15 digits).")

    if password and len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if password and not re.search(r"[A-Za-z]", password):
        errors.append("Password must include at least one letter.")
    if password and not re.search(r"\d", password):
        errors.append("Password must include at least one number.")

    if password != confirm_password:
        errors.append("Passwords do not match.")

    if errors:
        st.error(" | ".join(errors))
    else:
        payload = {
            "fullName": full_name.strip(),
            "email": email.strip().lower(),
            "phone": phone.strip(),
        }
        if password:
            payload["password"] = password

        try:
            with st.spinner("Updating your profile..."):
                resp = requests.put(UPDATE_PROFILE_URL, json=payload, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                st.success(" Profile updated successfully!")
                st.json({
                    "id": data["user"]["id"],
                    "fullName": data["user"]["fullName"],
                    "email": data["user"]["email"],
                    "phone": data["user"]["phone"],
                    "isActive": data["user"]["isActive"]
                })

            elif resp.status_code == 400:
                backend_msg = resp.json().get("message", "Bad Request")
                st.error(f" Error: {backend_msg}")

            else:
                st.error(f" Server error ({resp.status_code})")

        except requests.exceptions.RequestException as ex:
            st.error(" Could not connect to backend. Set DATABASE_URL or start the backend at " + CFG.API_BASE)

        except Exception:
            st.error(" Unexpected frontend error.")
            st.text(traceback.format_exc())
