import os
import traceback
from pathlib import Path

import requests
import streamlit as st

from config import CFG
from ui_helpers import require_login, auth_headers, log_bug, render_footer_bug_panel

REQUEST_DETAIL_URL = f"{CFG.API_BASE}/api/service-requests/{{}}"
UPDATE_ESTIMATE_STATUS_URL = f"{CFG.API_BASE}/api/service-requests/{{}}/estimate/status"

st.set_page_config(page_title="Carmate - Request Details", page_icon="", layout="centered")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
CSS_PATH = BASE_DIR / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

require_login()

rid = st.session_state.get("selected_request_id")
if not rid:
    st.warning("No request selected. Choose one from My Requests.")
    if st.button("Go to My Requests"):
        st.switch_page("pages/my_request.py")
    st.stop()

st.title("Request Details")
st.caption(f"Request ID: {rid}")

user_id = st.session_state.get("user", {}).get("id") or st.session_state.get("token")
r = None
used_db = False

if os.environ.get("DATABASE_URL") and user_id:
    try:
        from db import get_request_by_id
        with st.spinner("Loading request..."):
            row = get_request_by_id(rid, user_id)
        if row:
            used_db = True
            created_at = row.get("created_at")
            estimate = row.get("estimate") or {}
            r = {
                "id": str(row.get("id", "")),
                "vehicle": row.get("vehicle") or {},
                "serviceType": row.get("service_type") or "Service",
                "status": row.get("status") or "Pending",
                "createdAt": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at) if created_at else "",
                "estimate": estimate,
            }
        else:
            st.error("Request not found.")
            log_bug("Request details 404 (DB)", rid)
            st.stop()
    except Exception as e:
        st.error("Database error: " + str(e))
        log_bug("Request details DB error", traceback.format_exc())
        st.stop()

if not used_db:
    try:
        with st.spinner("Loading request..."):
            resp = requests.get(REQUEST_DETAIL_URL.format(rid), headers=auth_headers(), timeout=20)
        if resp.status_code == 200:
            r = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
        elif resp.status_code in (401, 403):
            st.error("Session expired. Please log in again.")
            log_bug("Request details auth", resp.text)
            st.stop()
        elif resp.status_code == 404:
            st.error("Request not found.")
            log_bug("Request details 404", rid)
            st.stop()
        else:
            st.error(f"Server error ({resp.status_code})")
            log_bug("Request details server", resp.text)
            st.stop()
    except requests.exceptions.RequestException as ex:
        st.error("Could not connect to backend. Set DATABASE_URL or start the backend at " + CFG.API_BASE)
        log_bug("Request details connection", str(ex))
        st.stop()
    except Exception:
        st.error("Unexpected error.")
        log_bug("Request details exception", traceback.format_exc())
        st.stop()

if not r:
    st.info("No request data.")
    st.stop()

vehicle = r.get("vehicle", {}) or {}
title = f"{vehicle.get('year','')} {vehicle.get('make','')} {vehicle.get('model','')}".strip()
status = r.get("status", "Pending")
service_type = r.get("serviceType", "Service")
created = r.get("createdAt", "")

with st.container(border=True):
    st.subheader("Request summary")
    st.markdown(f"**{service_type}** — *{status}*")
    st.write(title if title else "Vehicle info not available")
    if created:
        st.caption(f"Created: {created}")

# Vehicle photos
photos_list = []
if os.environ.get("DATABASE_URL"):
    try:
        from db import get_request_photos
        photos_list = get_request_photos(rid)
    except Exception:
        pass
elif r.get("photos"):
    photos_list = r.get("photos") if isinstance(r.get("photos"), list) else []

if photos_list:
    st.subheader("Vehicle photos")
    if os.environ.get("DATABASE_URL") and photos_list and isinstance(photos_list[0], dict) and photos_list[0].get("file_path"):
        cols = st.columns(min(len(photos_list), 3))
        for idx, photo in enumerate(photos_list):
            fp = photo.get("file_path")
            if fp:
                abs_path = PROJECT_ROOT / fp
                if abs_path.exists():
                    with cols[idx % 3]:
                        try:
                            st.image(str(abs_path), use_container_width=True)
                        except Exception:
                            st.caption("Photo")
    elif not os.environ.get("DATABASE_URL") and photos_list:
        for item in photos_list:
            url = item.get("url") or item.get("file_path") if isinstance(item, dict) else None
            if url:
                try:
                    st.image(url, use_container_width=True)
                except Exception:
                    st.caption("Photo")
else:
    st.caption("No vehicle photos uploaded yet.")

estimate = (r.get("estimate") or {})
if estimate:
    st.subheader("Estimate")

    currency = estimate.get("currency", "USD")
    labor = estimate.get("labor", 0)
    parts = estimate.get("parts", 0)
    tax = estimate.get("tax", 0)
    fees = estimate.get("fees", 0)
    total = estimate.get("total", None)
    notes = estimate.get("notes", "")
    valid_until = estimate.get("valid_until") or estimate.get("validUntil")
    est_status = (estimate.get("status") or "submitted").lower()

    if total is None:
        try:
            total = round(float(labor) + float(parts) + float(tax) + float(fees), 2)
        except Exception:
            total = ""

    with st.container(border=True):
        st.markdown(f"**Total:** {currency} {total}")
        st.write(f"Labor: {currency} {labor}")
        st.write(f"Parts: {currency} {parts}")
        st.write(f"Tax: {currency} {tax}")
        st.write(f"Fees: {currency} {fees}")

        if valid_until:
            st.caption(f"Valid until: {valid_until}")
        if notes:
            st.caption(f"Notes: {notes}")

        st.caption(f"Estimate status: {est_status}")

        if est_status in ("submitted", "pending", "quoted"):
            colA, colB = st.columns(2)
            with colA:
                if st.button("Accept Estimate", key=f"accept_est_{rid}"):
                    done = False
                    if os.environ.get("DATABASE_URL"):
                        try:
                            from db import update_estimate_status
                            if update_estimate_status(rid, "accepted"):
                                st.success("Estimate accepted.")
                                st.rerun()
                            else:
                                st.error("Could not accept estimate.")
                            done = True
                        except Exception as ex:
                            st.error("Database error: " + str(ex))
                            done = True
                    if not done:
                        try:
                            resp = requests.patch(
                                UPDATE_ESTIMATE_STATUS_URL.format(rid),
                                json={"status": "accepted"},
                                headers={**auth_headers(), "Content-Type": "application/json"},
                                timeout=20,
                            )
                            if resp.status_code in (200, 201):
                                st.success("Estimate accepted.")
                                st.rerun()
                            else:
                                st.error(f"Could not accept estimate ({resp.status_code})")
                                log_bug("Accept estimate error", resp.text)
                        except Exception as ex:
                            st.error("Error contacting server.")
                            log_bug("Accept estimate exception", str(ex))
            with colB:
                if st.button("Reject Estimate", key=f"reject_est_{rid}"):
                    done = False
                    if os.environ.get("DATABASE_URL"):
                        try:
                            from db import update_estimate_status
                            if update_estimate_status(rid, "rejected"):
                                st.success("Estimate rejected.")
                                st.rerun()
                            else:
                                st.error("Could not reject estimate.")
                            done = True
                        except Exception as ex:
                            st.error("Database error: " + str(ex))
                            done = True
                    if not done:
                        try:
                            resp = requests.patch(
                                UPDATE_ESTIMATE_STATUS_URL.format(rid),
                                json={"status": "rejected"},
                                headers={**auth_headers(), "Content-Type": "application/json"},
                                timeout=20,
                            )
                            if resp.status_code in (200, 201):
                                st.success("Estimate rejected.")
                                st.rerun()
                            else:
                                st.error(f"Could not reject estimate ({resp.status_code})")
                                log_bug("Reject estimate error", resp.text)
                        except Exception as ex:
                            st.error("Error contacting server.")
                            log_bug("Reject estimate exception", str(ex))
        else:
            st.info("This estimate is already finalized.")
else:
    st.info("No estimate has been submitted yet.")

st.divider()
if st.button("Back to My Requests"):
    st.switch_page("pages/my_request.py")
if st.button("Submit Estimate for this request"):
    st.session_state["selected_request_id"] = rid
    st.switch_page("pages/submit_estimate.py")

render_footer_bug_panel()
