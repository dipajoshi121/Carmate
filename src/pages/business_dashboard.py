import os
import traceback
from pathlib import Path

import streamlit as st

from ui_helpers import require_role, ROLE_BUSINESS, ROLE_ADMIN, mechanic_girl_background_css, log_bug, render_footer_bug_panel

st.set_page_config(page_title="Carmate - Business", page_icon="", layout="centered")

BASE_DIR = Path(__file__).resolve().parent
CSS_PATH = BASE_DIR / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
bg = mechanic_girl_background_css()
if bg:
    st.markdown(f"<style>{bg}</style>", unsafe_allow_html=True)

require_role(ROLE_BUSINESS, ROLE_ADMIN)

st.title("Business portfolio")
st.write(
    "Browse all open service requests. Open a request to review details and submit an estimate. "
    "You can edit requests that **your shop created** (walk-ins or on-behalf entries)."
)

uid = st.session_state.get("user", {}).get("id") or st.session_state.get("token")

if not os.environ.get("DATABASE_URL"):
    st.warning("Set **DATABASE_URL** so requests load from the database.")
    st.stop()

try:
    from db import list_all_service_requests, DatabaseError

    with st.spinner("Loading requests..."):
        all_req = list_all_service_requests()
except DatabaseError as e:
    st.error("Database error: " + str(e))
    st.info("Check DATABASE_URL and run: python run_migration.py")
    log_bug("Business dashboard DB", str(e))
    st.stop()
except Exception:
    st.error("Could not load requests.")
    log_bug("Business dashboard", traceback.format_exc())
    st.stop()

def _estimate_status(r: dict) -> str:
    est = r.get("estimate")
    if not isinstance(est, dict):
        return ""
    return (est.get("status") or "").strip().lower()


def _customer_accepted_estimate(r: dict) -> bool:
    return _estimate_status(r) == "accepted"


mine = [r for r in all_req if str(r.get("business_creator_id") or "") == str(uid)]
accepted_reqs = [r for r in all_req if _customer_accepted_estimate(r)]
other_reqs = [r for r in all_req if not _customer_accepted_estimate(r)]

mx1, mx2, mx3 = st.columns(3)
with mx1:
    st.metric("Requests your business logged", len(mine))
with mx2:
    st.metric("Total requests in system", len(all_req))
with mx3:
    st.metric("Estimates accepted by customers", len(accepted_reqs))

try:
    from db import business_rating_summary

    br = business_rating_summary(uid)
    if br and int(br.get("review_count") or 0) > 0 and br.get("avg_rating") is not None:
        st.metric("Your average rating", f"{float(br['avg_rating']):.2f} / 5", f"{int(br['review_count'])} review(s)")
    else:
        st.caption("Reviews will show here after customers complete jobs and submit ratings.")
except Exception:
    pass

c1, c2, c3 = st.columns(3)
with c1:
    if st.button("Create request", use_container_width=True):
        st.switch_page("pages/service_request.py")
with c2:
    if st.button("Submit estimate", use_container_width=True):
        st.switch_page("pages/submit_estimate.py")
with c3:
    if st.button("Upload photos", use_container_width=True):
        st.switch_page("pages/upload_vechile_photos.py")

st.divider()


def _request_card(r: dict, button_key_prefix: str):
    vid = str(r.get("id", ""))
    vehicle = r.get("vehicle") or {}
    title = f"{vehicle.get('year', '')} {vehicle.get('make', '')} {vehicle.get('model', '')}".strip()
    status = r.get("status") or "Pending"
    service_type = r.get("service_type") or "Service"
    is_mine = str(r.get("business_creator_id") or "") == str(uid)
    created_at = r.get("created_at")
    created_s = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at) if created_at else ""
    accepted = _customer_accepted_estimate(r)

    with st.container(border=True):
        if accepted:
            st.success("Customer accepted the estimate — proceed with the job or payment steps in request details.")
        st.markdown(f"**{service_type}** — *{status}*")
        if title:
            st.write(title)
        customer_notes = (r.get("description") or "").strip()
        if customer_notes:
            st.markdown("**Customer notes**")
            st.write(customer_notes)
        if is_mine:
            st.caption("You created this request")
        if created_s:
            st.caption(f"Created: {created_s}")
        if st.button("Open details", key=f"{button_key_prefix}_{vid}"):
            st.session_state["selected_request_id"] = vid
            st.switch_page("pages/request_details.py")


st.subheader("Estimates accepted by customers")
if not all_req:
    st.info("No requests yet.")
elif not accepted_reqs:
    st.info("No customers have accepted an estimate yet. Accepted jobs will appear here first.")
else:
    for r in accepted_reqs:
        _request_card(r, "biz_acc_open")

if all_req:
    st.divider()
    st.subheader("All other service requests")
    if not other_reqs:
        st.caption("No other requests — all current requests have an accepted estimate above.")
    else:
        for r in other_reqs:
            _request_card(r, "biz_open")

render_footer_bug_panel()
