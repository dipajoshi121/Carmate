from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
PAGES_DIR = BASE_DIR / "pages"
RES_DIR = PAGES_DIR / "resources"
CSS_PATH = RES_DIR / "carmate.css"

st.set_page_config(
    page_title="Carmate",
    page_icon="",
    layout="centered",
    initial_sidebar_state="collapsed",
)

if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

pages = {
    "": [
        st.Page("home.py", title="Home"),
    ],
    "Account": [
        st.Page("pages/login.py", title="Login"),
        st.Page("pages/register.py", title="Register"),
        st.Page("pages/forgot_password.py", title="Forgot Password"),
    ],
    "Services": [
        st.Page("pages/my_request.py", title="My Requests"),
        st.Page("pages/service_request.py", title="Create Request"),
        st.Page("pages/request_details.py", title="Request Details"),
        st.Page("pages/submit_estimate.py", title="Submit Estimate"),
        st.Page("pages/upload_vechile_photos.py", title="Upload Photos"),
    ],
    "Business": [
        st.Page("pages/business_dashboard.py", title="Business dashboard"),
    ],
    "Profile": [
        st.Page("pages/update_profile.py", title="Update Profile"),
    ],
    "Admin": [
        st.Page("pages/admin_dashboard.py", title="Admin dashboard"),
        st.Page("pages/view_users_registration.py", title="View Users"),
    ],
}

pg = st.navigation(pages, position="top")
pg.run()
