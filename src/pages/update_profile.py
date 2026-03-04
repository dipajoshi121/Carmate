import os
import re
import traceback
from pathlib import Path

import requests
import streamlit as st

from config import CFG
from ui_helpers import log_bug

UPDATE_PROFILE_URL = f"{CFG.API_BASE}/api/auth/updateProfile"
LOGOUT_URL = f"{CFG.API_BASE}/api/auth/logout"

st.set_page_config(page_title="Carmate - Update Profile", page_icon="", layout="centered")

BASE_DIR = Path(__file__).resolve().parent
CSS_PATH = BASE_DIR / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
else:
    st.warning(f"CSS file not found at: {CSS_PATH}")

if "token" not in st.session_state:
    st.warning("Please log in first.")
    if st.button("Go to Login"):
        st.switch_page("pages/login.py")
    st.stop()

user_id = st.session_state.get("user", {}).get("id") or st.session_state.get("token")
user_data = st.session_state.get("user", {})
if os.environ.get("DATABASE_URL") and user_id:
    try:
        from db import get_user_by_id
        db_user = get_user_by_id(user_id)
        if db_user:
            user_data = {
                "fullName": db_user.get("full_name") or "",
                "email": db_user.get("email") or "",
                "phone": db_user.get("phone") or "",
            }
    except Exception:
        pass

if not user_data.get("fullName") and not user_data.get("full_name"):
    user_data.setdefault("fullName", user_data.get("full_name", ""))
if not user_data.get("email"):
    user_data.setdefault("email", "")
if not user_data.get("phone"):
    user_data.setdefault("phone", "")

st.title("Update Your Profile")
st.write("Update your profile information below.")

if st.button("Logout"):
    if os.environ.get("DATABASE_URL"):
        if "token" in st.session_state:
            del st.session_state["token"]
        if "user" in st.session_state:
            del st.session_state["user"]
        st.success(" Logged out successfully!")
        st.switch_page("pages/login.py")
    else:
        try:
            resp = requests.post(LOGOUT_URL, timeout=10)
            if resp.status_code == 200:
                if "token" in st.session_state:
                    del st.session_state["token"]
                if "user" in st.session_state:
                    del st.session_state["user"]
                st.success(" Logged out successfully!")
                st.switch_page("pages/login.py")
            else:
                st.error(" Logout failed. Please try again.")
        except requests.exceptions.RequestException as ex:
            st.error(" Could not connect to backend. Set DATABASE_URL or start the backend at " + CFG.API_BASE)

display_name = user_data.get("fullName") or user_data.get("full_name") or ""
with st.form("update_profile_form", clear_on_submit=False):
    full_name = st.text_input("Full Name", placeholder="e.g., Arjun Khatri", value=display_name)
    email = st.text_input("Email", placeholder="e.g., arjun@example.com", value=user_data.get("email", ""))
    phone = st.text_input("Phone Number", placeholder="e.g., +1 555-555-5555", value=user_data.get("phone", ""))
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
        used_db = False
        if os.environ.get("DATABASE_URL") and user_id:
            try:
                from db import update_user
                with st.spinner("Updating your profile..."):
                    updated = update_user(
                        user_id,
                        full_name=full_name.strip(),
                        email=email.strip().lower(),
                        phone=phone.strip(),
                        password=password if password else None,
                    )
                if updated:
                    used_db = True
                    st.session_state["user"] = {
                        "id": str(updated.get("id", user_id)),
                        "email": updated.get("email"),
                        "fullName": updated.get("full_name"),
                        "phone": updated.get("phone"),
                        "isActive": updated.get("is_active"),
                    }
                    st.success(" Profile updated successfully!")
                    st.json({
                        "id": st.session_state["user"]["id"],
                        "fullName": st.session_state["user"]["fullName"],
                        "email": st.session_state["user"]["email"],
                        "phone": st.session_state["user"].get("phone", ""),
                        "isActive": st.session_state["user"].get("isActive", True),
                    })
                else:
                    st.error(" Could not update profile.")
            except Exception as e:
                st.error(" Database error: " + str(e))
                log_bug("Update profile DB", traceback.format_exc())

        if not used_db:
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
                    if "user" in data:
                        st.session_state["user"] = data["user"]
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
