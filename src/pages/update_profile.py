import os
import re
import traceback
from pathlib import Path

import requests
import streamlit as st

from config import CFG
from ui_helpers import log_bug, perform_logout

UPDATE_PROFILE_URL = f"{CFG.API_BASE}/api/auth/updateProfile"

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
role = (user_data.get("role") or "").strip().lower()
if os.environ.get("DATABASE_URL") and user_id:
    try:
        from db import get_user_by_id
        db_user = get_user_by_id(user_id)
        if db_user:
            user_data = {
                "fullName": db_user.get("full_name") or "",
                "email": db_user.get("email") or "",
                "phone": db_user.get("phone") or "",
                "address": db_user.get("address") or "",
                "role": db_user.get("role") or role,
            }
    except Exception:
        pass

if not user_data.get("fullName") and not user_data.get("full_name"):
    user_data.setdefault("fullName", user_data.get("full_name", ""))
if not user_data.get("email"):
    user_data.setdefault("email", "")
if not user_data.get("phone"):
    user_data.setdefault("phone", "")
if not user_data.get("address"):
    user_data.setdefault("address", "")

st.title("Update Your Profile")
st.write("Update your profile information below.")

if st.button("Logout"):
    perform_logout()
    st.success("Logged out successfully!")
    st.switch_page("pages/login.py")

display_name = user_data.get("fullName") or user_data.get("full_name") or ""
with st.form("update_profile_form", clear_on_submit=False):
    full_name = st.text_input("Full Name", placeholder="e.g., Arjun Khatri", value=display_name)
    email = st.text_input("Email", placeholder="e.g., arjun@example.com", value=user_data.get("email", ""))
    phone = st.text_input("Phone Number", placeholder="e.g., +1 555-555-5555", value=user_data.get("phone", ""))
    address = st.text_input("Address", placeholder="e.g., 123 Main St, City", value=user_data.get("address", ""))
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
                        address=address.strip() if address else None,
                        password=password if password else None,
                    )
                if updated:
                    used_db = True
                    st.session_state["user"] = {
                        "id": str(updated.get("id", user_id)),
                        "email": updated.get("email"),
                        "fullName": updated.get("full_name"),
                        "phone": updated.get("phone"),
                        "address": updated.get("address"),
                        "isActive": updated.get("is_active"),
                        "role": updated.get("role") or role,
                    }
                    st.success(" Profile updated successfully!")
                    name_line = (st.session_state["user"].get("fullName") or "").strip()
                    address_line = (st.session_state["user"].get("address") or "").strip()
                    if name_line and address_line:
                        st.info(f"{name_line} | {address_line}")
                    elif name_line:
                        st.info(name_line)
                    if st.session_state["user"].get("email"):
                        st.caption(f"Email: {st.session_state['user'].get('email')}")
                    if st.session_state["user"].get("phone"):
                        st.caption(f"Phone: {st.session_state['user'].get('phone')}")
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
                "address": address.strip(),
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
                    out_user = data.get("user") or {}
                    name_line = (out_user.get("fullName") or out_user.get("full_name") or "").strip()
                    address_line = (out_user.get("address") or "").strip()
                    if name_line and address_line:
                        st.info(f"{name_line} | {address_line}")
                    elif name_line:
                        st.info(name_line)
                    if out_user.get("email"):
                        st.caption(f"Email: {out_user.get('email')}")
                    if out_user.get("phone"):
                        st.caption(f"Phone: {out_user.get('phone')}")

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
