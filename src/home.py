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

st.subheader("Get started")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Login", use_container_width=True):
        st.switch_page("pages/login.py")
with col2:
    if st.button("Register", use_container_width=True):
        st.switch_page("pages/register.py")
with col3:
    if st.button("My Requests", use_container_width=True):
        st.switch_page("pages/my_request.py")

st.caption("Use the **menu above** to open Login, Register, My Requests, and other pages.")
