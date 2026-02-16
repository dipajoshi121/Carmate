# pages/my_requests.py

import traceback
from pathlib import Path

import requests
import streamlit as st

from config import CFG
from ui_helpers import require_login, auth_headers, log_bug, render_footer_bug_panel

# ------------------ API ------------------
MY_REQUESTS_URL = f"{CFG.API_BASE}/api/service-requests/me"

st.set_page_config(page_title="Carmate - My Requests", page_icon="📋", layout="centered")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
CSS_PATH = PROJECT_ROOT / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

require_login()

st.title("My Service Requests")
st.write("Your recent service requests are shown below.")

try:
    with st.spinner("Loading..."):
        resp = requests.get(MY_REQUESTS_URL, headers=auth_headers(), timeout=20)

    if resp.status_code == 200:
        items = resp.json() if "application/json" in resp.headers.get("content-type", "") else []

        if not items:
            st.info("No requests yet.")
            if st.button("Create a Request"):
                st.switch_page("pages/service_request.py")
        else:
            for r in items:
                rid = r.get("id") or r.get("_id") or "unknown"
                vehicle = r.get("vehicle", {}) or {}
                title = f"{vehicle.get('year','')} {vehicle.get('make','')} {vehicle.get('model','')}".strip()
                status = r.get("status", "Pending")
                service_type = r.get("serviceType", "Service")
                created = r.get("createdAt", "")

                with st.container(border=True):
                    st.markdown(f"**{service_type}** — *{status}*")
                    st.write(title if title else "Vehicle info not available")
                    if created:
                        st.caption(f"Created: {created}")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("View Details", key=f"view_{rid}"):
                            st.session_state["selected_request_id"] = rid
                            st.switch_page("pages/request_details.py")
                    with col2:
                        st.caption(f"Request ID: {rid}")

    elif resp.status_code in (401, 403):
        st.error("Session expired. Please login again.")
        log_bug("My requests auth", resp.text)
    else:
        st.error(f"Server error ({resp.status_code})")
        log_bug("My requests server", resp.text)

except requests.exceptions.RequestException as ex:
    st.error("Could not connect to backend API.")
    log_bug("My requests connection", str(ex))
except Exception:
    st.error("Unexpected error.")
    log_bug("My requests exception", traceback.format_exc())

render_footer_bug_panel()
