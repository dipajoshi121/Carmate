import streamlit as st
import requests
import json

# ------------------ API (BACKEND) ------------------
API_BASE = "http://localhost:8501"
USERS_URL = f"{API_BASE}/api/users"  # Endpoint for fetching registered users
TOGGLE_USER_URL = f"{API_BASE}/api/users/{{}}/toggle"  # Endpoint for activating/deactivating users

# ------------------ PAGE ------------------
st.set_page_config(page_title="View Registered Users", page_icon="👥", layout="centered")

# ------------------ LOAD USERS ------------------
def fetch_users():
    try:
        response = requests.get(USERS_URL)
        if response.status_code == 200:
            return response.json()  # Returns a list of users
        else:
            st.error("Failed to fetch users.")
            return []
    except requests.exceptions.RequestException as ex:
        st.error("Error fetching users from the server.")
        return []

# ------------------ TOGGLE USER STATUS ------------------
def toggle_user_status(user_id):
    try:
        response = requests.post(TOGGLE_USER_URL.format(user_id))
        if response.status_code == 200:
            return response.json()  # Success message
        else:
            st.error(f"Failed to update user status. Status code: {response.status_code}")
            return None
    except requests.exceptions.RequestException as ex:
        st.error("Error toggling user status.")
        return None

# ------------------ UI ------------------
st.title("View Registered Users")
st.write("Below is the list of registered users. You can activate or deactivate users.")

# ------------------ FETCH AND DISPLAY USERS ------------------
users = fetch_users()

if users:
    for user in users:
        st.write(f"**{user['name']}** ({user['email']}) - Status: {'Active' if user['is_active'] else 'Inactive'}")
        
        # Toggle button to activate/deactivate
        if st.button(f"Toggle Status for {user['name']}", key=user['id']):
            result = toggle_user_status(user['id'])
            if result:
                st.success(f"User status updated for {user['name']}.")
                st.experimental_rerun()  # Refresh the page after status change
else:
    st.write("No users found.")
