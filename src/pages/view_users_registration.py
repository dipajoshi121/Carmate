import os
from pathlib import Path

import requests
import streamlit as st

from config import CFG
from ui_helpers import require_login, auth_headers, log_bug, render_footer_bug_panel, require_role, ROLE_ADMIN

USERS_URL = f"{CFG.API_BASE}/api/users"
TOGGLE_USER_URL = f"{CFG.API_BASE}/api/users/{{}}/toggle"

st.set_page_config(page_title="View Registered Users", page_icon="", layout="centered")

BASE_DIR = Path(__file__).resolve().parent
CSS_PATH = BASE_DIR / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

require_role(ROLE_ADMIN)

def _display_name(user):
    """Normalize display name from API (name/fullName) or DB (full_name)."""
    return (
        user.get("name")
        or user.get("full_name")
        or user.get("fullName")
        or user.get("email")
        or "Unknown"
    )

def _user_is_active(user):
    return user.get("is_active", True)

def fetch_users():
    """Fetch users from DB when DATABASE_URL is set, otherwise from API."""
    if os.environ.get("DATABASE_URL"):
        try:
            from db import list_users
            raw = list_users()
            return [
                {
                    "id": str(r.get("id", "")),
                    "email": r.get("email", ""),
                    "name": r.get("full_name") or r.get("email") or "",
                    "full_name": r.get("full_name"),
                    "phone": r.get("phone"),
                    "is_active": bool(r.get("is_active", True)),
                    "role": (r.get("role") or "user"),
                    "created_at": r.get("created_at"),
                }
                for r in raw
            ]
        except Exception as e:
            st.error("Database error loading users: " + str(e))
            log_bug("View users DB error", str(e))
            return None

    try:
        response = requests.get(USERS_URL, headers=auth_headers(), timeout=20)
        if response.status_code == 200:
            data = response.json()
            return data if isinstance(data, list) else []
        if response.status_code in (401, 403):
            st.error("Session expired. Please log in again.")
            log_bug("View users auth", response.text)
            return None
        st.error("Failed to fetch users.")
        log_bug("View users server", response.text)
        return None
    except requests.exceptions.RequestException as ex:
        st.error("Could not connect to backend. Set DATABASE_URL or start the backend at " + CFG.API_BASE)
        log_bug("View users connection", str(ex))
        return None

def toggle_user_status(user_id, current_active: bool):
    """Toggle user active status via DB or API."""
    if os.environ.get("DATABASE_URL"):
        try:
            from db import set_user_active
            new_active = not current_active
            result = set_user_active(user_id, new_active)
            return result is not None
        except Exception as e:
            st.error("Database error updating user: " + str(e))
            log_bug("Toggle user DB error", str(e))
            return False

    try:
        response = requests.post(
            TOGGLE_USER_URL.format(user_id),
            headers=auth_headers(),
            timeout=20,
        )
        if response.status_code == 200:
            return True
        st.error(f"Failed to update user status. Status code: {response.status_code}")
        log_bug("Toggle user server", response.text)
        return False
    except requests.exceptions.RequestException as ex:
        st.error("Error toggling user status.")
        log_bug("Toggle user connection", str(ex))
        return False

st.title("View Registered Users")
st.write("Below is the list of registered users. You can activate or deactivate users.")

users = fetch_users()

if users is None:
    pass  # Error already shown
elif users:
    for user in users:
        uid = str(user.get("id", ""))
        name = _display_name(user)
        email = user.get("email", "")
        is_active = _user_is_active(user)
        with st.container(border=True):
            st.markdown(f"**{name}** — *{email}*")
            if user.get("phone"):
                st.caption(f"Phone: {user.get('phone')}")
            st.caption(f"Status: {'Active' if is_active else 'Inactive'} | Role: **{user.get('role', 'user')}**")
            if st.button(f"Toggle Status for {name}", key=f"toggle_{uid}"):
                if toggle_user_status(uid, is_active):
                    st.success(f"User status updated for {name}.")
                    st.rerun()
else:
    st.info("No users found.")

st.divider()
if st.button("Back to Home"):
    st.switch_page("home.py")

render_footer_bug_panel()
