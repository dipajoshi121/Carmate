from pathlib import Path

import streamlit as st

from ui_helpers import mechanic_girl_background_css, get_session_role, perform_logout, ROLE_USER, ROLE_BUSINESS, ROLE_ADMIN

BASE_DIR = Path(__file__).resolve().parent
PAGES_DIR = BASE_DIR / "pages"
RES_DIR = PAGES_DIR / "resources"
CSS_PATH = RES_DIR / "carmate.css"

if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
bg = mechanic_girl_background_css()
if bg:
    st.markdown(f"<style>{bg}</style>", unsafe_allow_html=True)

token = st.session_state.get("token")
qrole = get_session_role() if token else None

# Logged-in business: shop-only home (no customer marketing, sign-up, or consumer flows).
if token and qrole == ROLE_BUSINESS:
    st.title("Business portfolio")
    st.write("Manage incoming jobs, estimates, and vehicle photos for your shop.")
    st.divider()
    if st.button("Open dashboard", use_container_width=True):
        st.switch_page("pages/business_dashboard.py")
    if st.button("Log out", use_container_width=True):
        perform_logout()
        st.switch_page("home.py")
    st.caption("Use the top menu: Create request, Submit estimate, Upload photos, Profile.")
    st.stop()

# Logged-in customer: short welcome (no business/admin sign-up clutter).
if token and qrole == ROLE_USER:
    st.title("Carmate")
    st.write("Welcome back. Track your service requests or create a new one.")
    st.divider()
    if st.button("My requests", use_container_width=True):
        st.switch_page("pages/my_request.py")
    if st.button("Log out", use_container_width=True):
        perform_logout()
        st.switch_page("home.py")
    st.caption("Use the top menu for more actions.")
    st.stop()

# Logged-in admin: quick staff links only.
if token and qrole == ROLE_ADMIN:
    st.title("Carmate — Admin")
    st.write("Manage users, requests, and platform settings.")
    st.divider()
    a1, a2 = st.columns(2)
    with a1:
        if st.button("Admin dashboard", use_container_width=True):
            st.switch_page("pages/admin_dashboard.py")
    with a2:
        if st.button("Business portfolio", use_container_width=True):
            st.switch_page("pages/business_dashboard.py")
    if st.button("Log out", use_container_width=True):
        perform_logout()
        st.switch_page("home.py")
    st.caption("Use the top menu for full navigation.")
    st.stop()

# Logged out: public landing (customers & businesses can sign in / register).
st.title("Carmate")
st.markdown("**Connect with verified local car service providers.**")
st.write("Request vehicle services, compare quotes, and book appointments in one place.")

st.divider()

st.subheader("Sign in")
st.caption(
    "Each account type is separate: **customer** logins only work for customer accounts, "
    "**business** only for shop accounts, **admin** only for staff."
)
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("Customer login", use_container_width=True):
        st.session_state["login_intent"] = "user"
        st.switch_page("pages/login.py")
with c2:
    if st.button("Business login", use_container_width=True):
        st.session_state["login_intent"] = "business"
        st.switch_page("pages/login.py")
with c3:
    if st.button("Admin login", use_container_width=True):
        st.session_state["login_intent"] = "admin"
        st.switch_page("pages/login.py")

st.divider()

st.subheader("Create an account")
r1, r2 = st.columns(2)
with r1:
    if st.button("Register as customer", use_container_width=True):
        st.session_state["register_intent"] = "user"
        st.switch_page("pages/register.py")
with r2:
    if st.button("Register as business", use_container_width=True):
        st.session_state["register_intent"] = "business"
        st.switch_page("pages/register.py")
