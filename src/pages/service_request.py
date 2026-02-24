import traceback
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
    description = st.text_area("Description (optional)", placeholder="Describe the issue or service needed.")
    submitted = st.form_submit_button("Create Request")

if submitted:
    if not make or not model:
        st.error("Make and Model are required.")
    else:
        payload = {
            "vehicle": {"year": year, "make": make.strip(), "model": model.strip()},
            "serviceType": service_type,
            "description": (description or "").strip(),
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
