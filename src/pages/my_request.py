import os
import traceback
from pathlib import Path
import shutil

import requests
import streamlit as st

from config import CFG
from ui_helpers import require_login, auth_headers, log_bug, render_footer_bug_panel

MY_REQUESTS_URL = f"{CFG.API_BASE}/api/service-requests/me"
DELETE_REQUEST_URL = f"{CFG.API_BASE}/api/service-requests/{{}}"

st.set_page_config(page_title="Carmate - My Requests", page_icon="", layout="centered")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent  # project root for uploads/
CSS_PATH = BASE_DIR / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

require_login()

st.title("My Service Requests")
st.write("Your recent service requests are shown below.")

user_id = st.session_state.get("user", {}).get("id") or st.session_state.get("token")
items = []
used_db = False

if os.environ.get("DATABASE_URL") and user_id:
    try:
        from db import get_my_requests, DatabaseError
        with st.spinner("Loading..."):
            raw = get_my_requests(user_id)
        for r in raw:
            created_at = r.get("created_at")
            items.append({
                "id": str(r.get("id")),
                "_id": str(r.get("id")),
                "vehicle": r.get("vehicle") or {},
                "serviceType": r.get("service_type") or "Service",
                "status": r.get("status") or "Pending",
                "createdAt": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at) if created_at else "",
            })
        used_db = True
    except DatabaseError as e:
        st.error("Database error: " + str(e))
        st.info("Check DATABASE_URL and run: python run_migration.py")
        log_bug("My requests DB error", str(e))
        items = None
    except Exception:
        st.error("Could not load requests from the database.")
        log_bug("My requests DB error", traceback.format_exc())
        items = None

if not used_db:
    try:
        with st.spinner("Loading..."):
            resp = requests.get(MY_REQUESTS_URL, headers=auth_headers(), timeout=20)

        if resp.status_code == 200:
            items = resp.json() if "application/json" in resp.headers.get("content-type", "") else []
        elif resp.status_code in (401, 403):
            st.error("Session expired. Please login again.")
            log_bug("My requests auth", resp.text)
            items = None
        else:
            st.error(f"Server error ({resp.status_code})")
            log_bug("My requests server", resp.text)
            items = None
    except requests.exceptions.RequestException as ex:
        st.error("Could not connect to backend. Set DATABASE_URL and run the migration, or start the backend at " + CFG.API_BASE)
        log_bug("My requests connection", str(ex))
        items = None
    except Exception:
        st.error("Unexpected error.")
        log_bug("My requests exception", traceback.format_exc())
        items = None

if items is not None:
    if not items:
        st.info("No requests yet.")
        if st.button("Create a Request"):
            st.switch_page("pages/service_request.py")
    else:
        # Build simple friendly labels like Request 1, Request 2 ...
        friendly_labels = {}
        for idx, r in enumerate(items, start=1):
            rid_val = r.get("id") or r.get("_id") or f"req-{idx}"
            friendly_labels[str(rid_val)] = f"Request {idx}"
        st.session_state["request_labels"] = friendly_labels

        for idx, r in enumerate(items, start=1):
            rid = r.get("id") or r.get("_id") or "unknown"
            friendly_name = friendly_labels.get(str(rid), f"Request {idx}")
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

                photos = []
                if os.environ.get("DATABASE_URL"):
                    try:
                        from db import get_request_photos
                        photos = get_request_photos(rid)
                    except Exception:
                        pass
                if photos:
                    st.caption(f"{len(photos)} photo(s)")
                    cols = st.columns(min(len(photos), 4))
                    for idx, photo in enumerate(photos[:4]):
                        fp = photo.get("file_path")
                        if fp:
                            abs_path = PROJECT_ROOT / fp
                            if abs_path.exists():
                                with cols[idx % len(cols)]:
                                    try:
                                        st.image(str(abs_path), caption="", use_container_width=True)
                                    except Exception:
                                        st.caption("Photo")

                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("View Details", key=f"view_{rid}"):
                        st.session_state["selected_request_id"] = rid
                        st.switch_page("pages/request_details.py")
                with col2:
                    st.caption(f"{friendly_name}")
                with col3:
                    if st.button("Delete Request", key=f"delete_{rid}"):
                        delete_error = None
                        deleted = False
                        if os.environ.get("DATABASE_URL") and user_id:
                            try:
                                from db import delete_service_request
                                if delete_service_request(rid, user_id):
                                    deleted = True
                                    uploads_root = PROJECT_ROOT / "uploads" / rid
                                    try:
                                        if uploads_root.exists():
                                            shutil.rmtree(uploads_root)
                                    except Exception:
                                        pass
                                else:
                                    delete_error = "Could not delete request in the database."
                            except Exception as ex:
                                delete_error = "Database error: " + str(ex)
                        if not deleted:
                            try:
                                resp = requests.delete(
                                    DELETE_REQUEST_URL.format(rid),
                                    headers=auth_headers(),
                                    timeout=20,
                                )
                                if resp.status_code in (200, 204):
                                    deleted = True
                                elif resp.status_code in (401, 403):
                                    delete_error = "Session expired. Please login again."
                                else:
                                    delete_error = f"Could not delete request ({resp.status_code})."
                            except requests.exceptions.RequestException as ex:
                                delete_error = "Could not contact backend: " + str(ex)
                            except Exception as ex:
                                delete_error = "Unexpected error: " + str(ex)
                        if deleted:
                            st.success("Request deleted.")
                            st.rerun()
                        elif delete_error:
                            st.error(delete_error)

render_footer_bug_panel()
