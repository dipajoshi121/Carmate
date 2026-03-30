import os
import traceback
from datetime import date, time as time_cls
from pathlib import Path

import requests
import streamlit as st

from config import CFG
from ui_helpers import require_login, auth_headers, log_bug, render_footer_bug_panel

CREATE_REQUEST_URL = f"{CFG.API_BASE}/api/service-requests"

st.set_page_config(page_title="Carmate - New Service Request", page_icon="", layout="centered")

BASE_DIR = Path(__file__).resolve().parent
CSS_PATH = BASE_DIR / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

require_login()

st.title("Create Service Request")
st.write("Submit a new vehicle service request. We'll match you with verified providers.")

with st.form("service_request_form", clear_on_submit=False):
    st.subheader("Vehicle")
    year = st.number_input("Year", min_value=1990, max_value=2030, value=2020, step=1)
    make = st.text_input("Make", placeholder="e.g. Toyota, Honda")
    model = st.text_input("Model", placeholder="e.g. Camry, Civic")
    st.subheader("Service")
    service_type = st.selectbox(
        "Service type",
        ["Oil Change", "Brake Service", "Tire Rotation", "Inspection", "Repair", "Other"],
    )
    preferred_date = st.date_input("Preferred service date", value=date.today())
    col_time_h, col_time_m = st.columns(2)
    with col_time_h:
        hour = st.number_input("Hour (24h)", min_value=0, max_value=23, value=10, step=1)
    with col_time_m:
        minute = st.number_input("Minute", min_value=0, max_value=59, value=0, step=15)
    description = st.text_area("Description (optional)", placeholder="Describe the issue or service needed.")
    submitted = st.form_submit_button("Create Request")

if submitted:
    if not make or not model:
        st.error("Make and Model are required.")
    else:
        vehicle = {"year": year, "make": make.strip(), "model": model.strip()}
        description_clean = (description or "").strip()
        preferred_at = None
        try:
            preferred_at = time_cls(int(hour), int(minute))
        except Exception:
            preferred_at = None
        user_id = st.session_state.get("user", {}).get("id") or st.session_state.get("token")
        db_mode = bool(os.environ.get("DATABASE_URL"))
        used_db = False

        if db_mode and user_id:
            try:
                from db import create_service_request
                with st.spinner("Creating request..."):
                    created = create_service_request(
                        user_id,
                        vehicle,
                        service_type,
                        description_clean,
                        preferred_date=preferred_date,
                        preferred_time=preferred_at,
                    )
                if created:
                    used_db = True
                    req_id = str(created.get("id", ""))
                    st.session_state["selected_request_id"] = req_id
                    st.success("Service request created successfully!")
                    st.info(f"Request ID: **{req_id}**")
                    if st.button("View this request"):
                        st.switch_page("pages/request_details.py")
                    if st.button("Go to My Requests"):
                        st.switch_page("pages/my_request.py")
                else:
                    used_db = True
                    st.error("Could not create request. Please try again.")
                    log_bug("Create request DB", "create_service_request returned None")
            except Exception as e:
                used_db = True
                st.error("Database error: " + str(e))
                st.info("Check DATABASE_URL and run: python run_migration.py")
                log_bug("Create request DB error", traceback.format_exc())

        if not used_db:
            payload = {
                "vehicle": vehicle,
                "serviceType": service_type,
                "description": description_clean,
                "preferredDate": preferred_date.isoformat() if preferred_date else None,
                "preferredTime": preferred_at.strftime("%H:%M") if preferred_at else None,
            }
            try:
                with st.spinner("Creating request..."):
                    resp = requests.post(
                        CREATE_REQUEST_URL,
                        json=payload,
                        headers={**auth_headers(), "Content-Type": "application/json"},
                        timeout=20,
                    )
                if resp.status_code in (200, 201):
                    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    req_id = data.get("id") or data.get("_id") or data.get("requestId")
                    st.success("Service request created successfully!")
                    if req_id:
                        st.session_state["selected_request_id"] = req_id
                        st.info(f"Request ID: **{req_id}**")
                        if st.button("View this request"):
                            st.switch_page("pages/request_details.py")
                        if st.button("Go to My Requests"):
                            st.switch_page("pages/my_request.py")
                elif resp.status_code in (401, 403):
                    st.error("Session expired. Please log in again.")
                    log_bug("Create request auth", resp.text)
                elif resp.status_code == 400:
                    try:
                        msg = resp.json().get("message", "Bad Request")
                    except Exception:
                        msg = resp.text
                    st.error(msg)
                    log_bug("Create request (400)", msg)
                else:
                    st.error(f"Server error ({resp.status_code})")
                    log_bug("Create request server", resp.text)
            except requests.exceptions.RequestException as ex:
                st.error("Could not connect to backend. Set DATABASE_URL or start the backend at " + CFG.API_BASE)
                log_bug("Create request connection", str(ex))
            except Exception:
                st.error("Unexpected error.")
                log_bug("Create request exception", traceback.format_exc())

st.divider()
if st.button("Back to My Requests"):
    st.switch_page("pages/my_request.py")

render_footer_bug_panel()
