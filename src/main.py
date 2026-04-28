from pathlib import Path

import streamlit as st

from ui_helpers import ROLE_ADMIN, ROLE_BUSINESS, ROLE_USER, get_session_role

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

logged_in = bool(st.session_state.get("token"))
role = get_session_role() if logged_in else None

if not logged_in:
    st.markdown(
        """
        <style>
        [data-testid="stNavigation"] { visibility: hidden !important; height: 0 !important; min-height: 0 !important; overflow: hidden !important; padding: 0 !important; margin: 0 !important; }
        [data-testid="stHeader"] [data-testid="stDecoration"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _p(path: str, title: str):
    return st.Page(path, title=title)


# Full list: required when logged out so st.switch_page(...) after login/register always resolves.
pages_logged_out = {
    "": [_p("home.py", "Home")],
    "Account": [
        _p("pages/login.py", "Login"),
        _p("pages/register.py", "Register"),
        _p("pages/forgot_password.py", "Forgot Password"),
        _p("pages/logout.py", "Logout"),
    ],
    "Services": [
        _p("pages/my_request.py", "My Requests"),
        _p("pages/service_request.py", "Create Request"),
        _p("pages/request_details.py", "Request Details"),
        _p("pages/view_ratings.py", "View ratings"),
        _p("pages/submit_estimate.py", "Submit Estimate"),
        _p("pages/upload_vechile_photos.py", "Upload Photos"),
    ],
    "Business": [
        _p("pages/business_dashboard.py", "Business portfolio"),
    ],
    "Profile": [
        _p("pages/update_profile.py", "Update Profile"),
    ],
    "Admin": [
        _p("pages/admin_dashboard.py", "Admin dashboard"),
        _p("pages/view_users_registration.py", "View Users"),
    ],
}

# Customer: no business tools, no estimates, no admin.
pages_customer = {
    "": [_p("home.py", "Home")],
    "Account": [
        _p("pages/login.py", "Login"),
        _p("pages/register.py", "Register"),
        _p("pages/forgot_password.py", "Forgot Password"),
        _p("pages/logout.py", "Logout"),
    ],
    "Services": [
        _p("pages/my_request.py", "My Requests"),
        _p("pages/service_request.py", "Create Request"),
        _p("pages/request_details.py", "Request Details"),
        _p("pages/view_ratings.py", "View ratings"),
        _p("pages/upload_vechile_photos.py", "Upload Photos"),
    ],
    "Profile": [
        _p("pages/update_profile.py", "Update Profile"),
    ],
}

# Business: no customer "My Requests" list; estimates and shop dashboard are here.
pages_business = {
    "": [_p("home.py", "Home")],
    "Account": [
        _p("pages/login.py", "Login"),
        _p("pages/register.py", "Register"),
        _p("pages/forgot_password.py", "Forgot Password"),
        _p("pages/logout.py", "Logout"),
    ],
    "Services": [
        _p("pages/service_request.py", "Create Request"),
        _p("pages/request_details.py", "Request Details"),
        _p("pages/view_ratings.py", "View ratings"),
        _p("pages/submit_estimate.py", "Submit Estimate"),
        _p("pages/upload_vechile_photos.py", "Upload Photos"),
    ],
    "Business": [
        _p("pages/business_dashboard.py", "Business portfolio"),
    ],
    "Profile": [
        _p("pages/update_profile.py", "Update Profile"),
    ],
}

if not logged_in:
    pages = pages_logged_out
elif role == ROLE_USER:
    pages = pages_customer
elif role == ROLE_BUSINESS:
    pages = pages_business
else:
    pages = pages_logged_out

pg = st.navigation(pages, position="top")
pg.run()
