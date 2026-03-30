import os
import traceback
from pathlib import Path

import streamlit as st

from ui_helpers import require_role, ROLE_ADMIN, mechanic_girl_background_css, log_bug, render_footer_bug_panel
from ui_helpers import ROLE_USER, ROLE_BUSINESS

st.set_page_config(page_title="Carmate - Admin", page_icon="", layout="centered")

BASE_DIR = Path(__file__).resolve().parent
CSS_PATH = BASE_DIR / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
bg = mechanic_girl_background_css()
if bg:
    st.markdown(f"<style>{bg}</style>", unsafe_allow_html=True)

require_role(ROLE_ADMIN)

st.title("Admin dashboard")
st.write("Manage user roles and review or edit any service request.")

uid = st.session_state.get("user", {}).get("id") or st.session_state.get("token")

st.subheader("Users & roles")
if not os.environ.get("DATABASE_URL"):
    st.warning("Set **DATABASE_URL** to manage users and requests from the database.")
else:
    from db import list_users, set_user_role, list_all_service_requests, DatabaseError

    try:
        users = list_users()
        role_options = [ROLE_USER, ROLE_BUSINESS, ROLE_ADMIN]
        for u in users:
            u_id = str(u.get("id", ""))
            if u_id == str(uid):
                st.caption(f"**{u.get('email')}** (you) — role: {u.get('role') or 'user'}")
                continue
            with st.container(border=True):
                st.write(f"**{u.get('full_name') or u.get('email')}** — {u.get('email')}")
                current = (u.get("role") or ROLE_USER).strip().lower()
                if current not in role_options:
                    current = ROLE_USER
                col_a, col_b = st.columns([2, 1])
                with col_a:
                    new_role = st.selectbox(
                        "Role",
                        role_options,
                        index=role_options.index(current) if current in role_options else 0,
                        key=f"role_sel_{u_id}",
                    )
                with col_b:
                    if st.button("Apply role", key=f"apply_role_{u_id}"):
                        try:
                            set_user_role(u_id, new_role)
                            st.success("Role updated.")
                            st.rerun()
                        except Exception as ex:
                            st.error(str(ex))
                            log_bug("set_user_role", str(ex))
    except DatabaseError as e:
        st.error(str(e))
        users = []
    except Exception:
        log_bug("admin users", traceback.format_exc())
        st.error("Could not load users.")
        users = []

    st.divider()
    st.subheader("All service requests")
    try:
        all_req = list_all_service_requests()
    except DatabaseError as e:
        st.error(str(e))
        all_req = []
    except Exception:
        log_bug("admin requests list", traceback.format_exc())
        all_req = []

    if not all_req:
        st.info("No service requests.")
    else:
        for r in all_req:
            vid = str(r.get("id", ""))
            vehicle = r.get("vehicle") or {}
            title = f"{vehicle.get('year', '')} {vehicle.get('make', '')} {vehicle.get('model', '')}".strip()
            status = r.get("status") or "Pending"
            service_type = r.get("service_type") or "Service"
            with st.container(border=True):
                st.markdown(f"**{service_type}** — *{status}*")
                if title:
                    st.write(title)
                if st.button("Open / edit", key=f"adm_open_{vid}"):
                    st.session_state["selected_request_id"] = vid
                    st.switch_page("pages/request_details.py")

st.divider()
if st.button("Registered users (details & activate)"):
    st.switch_page("pages/view_users_registration.py")
if st.button("Home"):
    st.switch_page("home.py")

render_footer_bug_panel()
