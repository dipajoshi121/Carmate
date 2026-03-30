from pathlib import Path

import streamlit as st

from ui_helpers import mechanic_girl_background_css

BASE_DIR = Path(__file__).resolve().parent
PAGES_DIR = BASE_DIR / "pages"
RES_DIR = PAGES_DIR / "resources"
CSS_PATH = RES_DIR / "carmate.css"

if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
bg = mechanic_girl_background_css()
if bg:
    st.markdown(f"<style>{bg}</style>", unsafe_allow_html=True)

st.title("Carmate")
st.markdown("**Connect with verified local car service providers.**")
st.write("Request vehicle services, compare quotes, and book appointments in one place.")

st.divider()

st.subheader("Sign in")
st.caption(
    "Each account type is separate: **customer** logins only work for customer accounts, "
    "**business** only for shop accounts, **admin** only for staff. Admins can manage both sides from the admin dashboard."
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

st.divider()

st.subheader("Quick links")
q1, q2, q3 = st.columns(3)
with q1:
    if st.button("My requests (customers)", use_container_width=True):
        st.switch_page("pages/my_request.py")
with q2:
    if st.button("Business dashboard", use_container_width=True):
        st.switch_page("pages/business_dashboard.py")
with q3:
    if st.button("Admin dashboard", use_container_width=True):
        st.switch_page("pages/admin_dashboard.py")

st.caption("Use the top menu to open other pages after you sign in.")
