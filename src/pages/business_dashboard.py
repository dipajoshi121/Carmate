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

mine = [r for r in all_req if str(r.get("business_creator_id") or "") == str(uid)]
st.metric("Requests your business logged", len(mine))
st.caption(f"Total requests in system: **{len(all_req)}**")

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
st.subheader("All service requests")

if not all_req:
    st.info("No requests yet.")
else:
    for r in all_req:
        vid = str(r.get("id", ""))
        vehicle = r.get("vehicle") or {}
        title = f"{vehicle.get('year', '')} {vehicle.get('make', '')} {vehicle.get('model', '')}".strip()
        status = r.get("status") or "Pending"
        service_type = r.get("service_type") or "Service"
        is_mine = str(r.get("business_creator_id") or "") == str(uid)
        created_at = r.get("created_at")
        created_s = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at) if created_at else ""

        with st.container(border=True):
            st.markdown(f"**{service_type}** — *{status}*")
            if title:
                st.write(title)
            if is_mine:
                st.caption("You created this request")
            if created_s:
                st.caption(f"Created: {created_s}")
            if st.button("Open details", key=f"biz_open_{vid}"):
                st.session_state["selected_request_id"] = vid
                st.switch_page("pages/request_details.py")

render_footer_bug_panel()
