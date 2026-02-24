import streamlit as st
import requests
from pathlib import Path

from config import CFG

USERS_URL = f"{CFG.API_BASE}/api/users"
TOGGLE_USER_URL = f"{CFG.API_BASE}/api/users/{{}}/toggle"

st.set_page_config(page_title="View Registered Users", page_icon="👥", layout="centered")

BASE_DIR = Path(__file__).resolve().parent
CSS_PATH = BASE_DIR / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

def fetch_users():
    try:
        response = requests.get(USERS_URL)
        if response.status_code == 200:
            return response.json()
        else:
            st.error("Failed to fetch users.")
            return []
    except requests.exceptions.RequestException as ex:
        st.error("Error fetching users from the server.")
        return []

def toggle_user_status(user_id):
    try:
        response = requests.post(TOGGLE_USER_URL.format(user_id))
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to update user status. Status code: {response.status_code}")
            return None
    except requests.exceptions.RequestException as ex:
        st.error("Error toggling user status.")
        return None

st.title("View Registered Users")
st.write("Below is the list of registered users. You can activate or deactivate users.")

users = fetch_users()

if users:
    for user in users:
        st.write(f"**{user['name']}** ({user['email']}) - Status: {'Active' if user['is_active'] else 'Inactive'}")
        if st.button(f"Toggle Status for {user['name']}", key=user['id']):
            result = toggle_user_status(user['id'])
            if result:
                st.success(f"User status updated for {user['name']}.")
                st.rerun()
else:
    st.write("No users found.")

st.divider()
if st.button("Back to Home"):
    st.switch_page("main.py")
