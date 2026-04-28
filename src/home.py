import os
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


def _render_public_ratings_preview():
    st.subheader("Public business ratings")
    if not os.environ.get("DATABASE_URL"):
        st.caption("Ratings become visible when DATABASE_URL is configured.")
    else:
        try:
            from db import list_businesses_with_ratings

            rated = [r for r in list_businesses_with_ratings() if int(r.get("review_count") or 0) > 0]
        except Exception:
            rated = []
        if not rated:
            st.caption("No public ratings yet.")
        else:
            for row in rated[:5]:
                name = (row.get("full_name") or "").strip() or (row.get("email") or "Business")
                address = (row.get("address") or "").strip()
                avg = float(row.get("avg_rating") or 0)
                cnt = int(row.get("review_count") or 0)
                stars = min(5, max(1, int(round(avg))))
                label = f"**{name}**"
                if address:
                    label += f" — {address}"
                label += " — " + ("★" * stars + "☆" * (5 - stars)) + f" ({avg:.2f}/5, {cnt} review(s))"
                st.markdown(label)
    if st.button("View all public ratings", use_container_width=True, key="home_public_ratings"):
        st.switch_page("pages/view_ratings.py")

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
    _render_public_ratings_preview()
    st.caption("Use the top menu: Create request, Submit estimate, Upload photos, Profile.")
    st.stop()

# Logged-in customer: short welcome (no business/admin sign-up clutter).
if token and qrole == ROLE_USER:
    st.title("Carmate")
    st.write("Welcome back. Track your service requests or create a new one.")
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("My requests", use_container_width=True):
            st.switch_page("pages/my_request.py")
    with c2:
        if st.button("View business ratings", use_container_width=True):
            st.switch_page("pages/view_ratings.py")
    if st.button("Log out", use_container_width=True):
        perform_logout()
        st.switch_page("home.py")
    _render_public_ratings_preview()
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
    _render_public_ratings_preview()
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

st.divider()
_render_public_ratings_preview()
