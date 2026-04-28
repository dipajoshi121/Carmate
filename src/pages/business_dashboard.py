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
    from db import list_all_service_requests, list_request_estimates, update_service_request_fields, DatabaseError

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


accepted_request_ids = set()
accepted_for_me = []
for _r in all_req:
    rid_val = str(_r.get("id", ""))
    if not rid_val:
        continue
    try:
        est_rows = list_request_estimates(rid_val)
        if any((e.get("status") or "").strip().lower() == "accepted" for e in est_rows):
            accepted_request_ids.add(rid_val)
        mine_here = [
            e
            for e in est_rows
            if str(e.get("business_user_id") or "") == str(uid)
        ]
        accepted_mine = next(
            (e for e in mine_here if (e.get("status") or "").strip().lower() == "accepted"),
            None,
        )
        if accepted_mine:
            accepted_for_me.append({
                "request": _r,
                "estimate": accepted_mine,
            })
    except Exception:
        # Keep dashboard resilient; fallback to legacy estimate JSON below.
        pass


def _customer_accepted_estimate(r: dict) -> bool:
    rid_val = str(r.get("id", ""))
    return rid_val in accepted_request_ids or _estimate_status(r) == "accepted"


def _job_completed(r: dict) -> bool:
    return (r.get("status") or "").strip().lower() == "completed"


mine = [r for r in all_req if str(r.get("business_creator_id") or "") == str(uid)]
accepted_reqs = [r for r in all_req if _customer_accepted_estimate(r)]
completed_reqs = [r for r in all_req if _job_completed(r)]
pending_reqs = [r for r in all_req if (r.get("status") or "").strip().lower() == "pending"]
other_reqs = [r for r in all_req if not _customer_accepted_estimate(r)]

mx1, mx2, mx3, mx4, mx5 = st.columns(5)
with mx1:
    st.metric("Requests your business logged", len(mine))
with mx2:
    st.metric("Total requests in system", len(all_req))
with mx3:
    st.metric("Estimates accepted by customers", len(accepted_reqs))
with mx4:
    st.metric("Completed jobs", len(completed_reqs))
with mx5:
    st.metric("Your accepted quotes", len(accepted_for_me))

try:
    from db import business_rating_summary

    br = business_rating_summary(uid)
    if br and int(br.get("review_count") or 0) > 0 and br.get("avg_rating") is not None:
        st.metric("Your average rating", f"{float(br['avg_rating']):.2f} / 5", f"{int(br['review_count'])} review(s)")
    else:
        st.caption("Reviews will show here after customers complete jobs and submit ratings.")
except Exception:
    pass

c1, c2 = st.columns(2)
with c1:
    if st.button("Submit estimate", use_container_width=True):
        st.switch_page("pages/submit_estimate.py")
with c2:
    if st.button("Upload photos", use_container_width=True):
        st.switch_page("pages/upload_vechile_photos.py")

st.divider()

st.subheader("Accepted quotations for your business")
if not accepted_for_me:
    st.caption("No customer has accepted your quote yet.")
else:
    st.success(f"You have {len(accepted_for_me)} accepted quote(s).")
    for item in accepted_for_me:
        req = item["request"]
        est = item["estimate"]
        rid = str(req.get("id", ""))
        vehicle = req.get("vehicle") or {}
        title = f"{vehicle.get('year', '')} {vehicle.get('make', '')} {vehicle.get('model', '')}".strip()
        quote_total = est.get("total")
        quote_ccy = (est.get("currency") or "USD").upper()
        with st.container(border=True):
            st.markdown("**Customer accepted your quotation**")
            if title:
                st.write(title)
            st.caption(f"Accepted price: {quote_ccy} {quote_total}")
            b1, b2 = st.columns(2)
            with b1:
                if st.button("Open accepted request", key=f"biz_open_acc_me_{rid}", use_container_width=True):
                    st.session_state["selected_request_id"] = rid
                    st.switch_page("pages/request_details.py")
            with b2:
                already_completed = (req.get("status") or "").strip().lower() == "completed"
                if already_completed:
                    st.button(
                        "Completed",
                        key=f"biz_done_acc_me_{rid}",
                        disabled=True,
                        use_container_width=True,
                    )
                else:
                    if st.button(
                        "Mark completed",
                        key=f"biz_mark_done_acc_me_{rid}",
                        use_container_width=True,
                    ):
                        try:
                            out = update_service_request_fields(rid, status="Completed")
                            if out:
                                st.success("Job marked as completed.")
                                st.rerun()
                            else:
                                st.error("Could not mark this request as completed.")
                        except Exception as ex:
                            st.error("Database error: " + str(ex))
                            log_bug("business dashboard mark completed", str(ex))

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
        if _job_completed(r):
            st.success("Job completed")
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
    st.subheader("Pending requests")
    if not pending_reqs:
        st.caption("No pending requests right now.")
    else:
        for r in pending_reqs:
            _request_card(r, "biz_pending_open")

if all_req:
    st.divider()
    st.subheader("Completed requests")
    if not completed_reqs:
        st.caption("No completed requests yet.")
    else:
        for r in completed_reqs:
            _request_card(r, "biz_completed_open")

if all_req:
    st.divider()
    st.subheader("All other service requests")
    if not other_reqs:
        st.caption("No other requests — all current requests have an accepted estimate above.")
    else:
        for r in other_reqs:
            _request_card(r, "biz_open")

render_footer_bug_panel()
