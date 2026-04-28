import os
import traceback
from datetime import date, timedelta
from pathlib import Path

import requests
import streamlit as st

from config import CFG
from ui_helpers import (
    require_role,
    auth_headers,
    log_bug,
    render_footer_bug_panel,
    ROLE_BUSINESS,
    ROLE_ADMIN,
    get_session_role,
)

SUBMIT_ESTIMATE_URL = f"{CFG.API_BASE}/api/service-requests/{{}}/estimate"

st.set_page_config(page_title="Carmate - Submit Estimate", page_icon="", layout="centered")

BASE_DIR = Path(__file__).resolve().parent
CSS_PATH = BASE_DIR / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

require_role(ROLE_BUSINESS, ROLE_ADMIN)

st.title("Submit Estimate")
st.write("Submit an estimated cost so the customer knows the expected service cost.")
if os.environ.get("DATABASE_URL"):
    try:
        from db import business_rating_summary

        _biz_uid = st.session_state.get("user", {}).get("id") or st.session_state.get("token")
        _summary = business_rating_summary(str(_biz_uid)) if _biz_uid else None
        _rc = int((_summary or {}).get("review_count") or 0)
        _avg = (_summary or {}).get("avg_rating")
        if _rc > 0 and _avg is not None:
            st.caption(f"Your public rating: {float(_avg):.2f}/5 based on {_rc} review(s).")
    except Exception:
        pass

prefill_rid = st.session_state.get("selected_request_id", "")
request_id = st.text_input("Service Request ID", value=prefill_rid, placeholder="Paste the request ID here")
if request_id and request_id.strip():
    if st.button("Open request chat/details", key="open_chat_from_submit_est"):
        st.session_state["selected_request_id"] = request_id.strip()
        st.switch_page("pages/request_details.py")

with st.form("estimate_form", clear_on_submit=False):
    col1, col2 = st.columns(2)

    with col1:
        currency = st.text_input("Currency", value="USD")
        labor = st.number_input("Labor Amount", min_value=0.0, step=1.0, value=0.0)
        parts = st.number_input("Parts Amount", min_value=0.0, step=1.0, value=0.0)

    with col2:
        tax = st.number_input("Tax Amount", min_value=0.0, step=0.5, value=0.0)
        fees = st.number_input("Fees Amount", min_value=0.0, step=0.5, value=0.0)
        valid_until = st.date_input("Valid Until", value=date.today() + timedelta(days=7))

    notes = st.text_area("Notes (optional)", placeholder="What does this estimate include?", height=90)

    submitted = st.form_submit_button("Submit Estimate")

total = round(float(labor) + float(parts) + float(tax) + float(fees), 2)
st.caption(f"Estimated Total: {currency.strip().upper()} {total}")

if submitted:
    if not request_id or not request_id.strip():
        st.error("Service Request ID is required.")
    else:
        req_id_clean = request_id.strip()
        estimate_payload = {
            "currency": currency.strip().upper(),
            "labor": float(labor),
            "parts": float(parts),
            "tax": float(tax),
            "fees": float(fees),
            "total": total,
            "notes": notes.strip(),
            "valid_until": valid_until.isoformat() if valid_until else None,
            "status": "submitted",
        }
        used_db = False

        if os.environ.get("DATABASE_URL"):
            try:
                from db import upsert_request_estimate
                biz_uid = st.session_state.get("user", {}).get("id") or st.session_state.get("token")
                biz_name = (
                    st.session_state.get("user", {}).get("fullName")
                    or st.session_state.get("user", {}).get("full_name")
                    or st.session_state.get("user", {}).get("email")
                    or "Business"
                )
                with st.spinner("Submitting estimate..."):
                    result = upsert_request_estimate(
                        request_id=req_id_clean,
                        business_user_id=str(biz_uid),
                        business_name=str(biz_name),
                        estimate=estimate_payload,
                    )
                if result:
                    used_db = True
                    st.success("Estimate submitted successfully!")
                    st.caption("The customer can now compare this estimate with other business quotes.")
                    if st.button("Open request chat", key=f"open_chat_after_submit_db_{req_id_clean}"):
                        st.session_state["selected_request_id"] = req_id_clean
                        st.switch_page("pages/request_details.py")
                else:
                    st.error("Request not found or could not update estimate.")
                    log_bug("Submit estimate DB", "upsert_request_estimate returned None")
            except Exception as e:
                st.error("Database error: " + str(e))
                log_bug("Submit estimate DB error", traceback.format_exc())

        if not used_db:
            try:
                with st.spinner("Submitting estimate..."):
                    resp = requests.patch(
                        SUBMIT_ESTIMATE_URL.format(req_id_clean),
                        json=estimate_payload,
                        headers={**auth_headers(), "Content-Type": "application/json"},
                        timeout=20,
                    )

                if resp.status_code in (200, 201):
                    st.success("Estimate submitted successfully!")
                    st.caption("The customer can review this estimate from their request details.")
                    if st.button("Open request chat", key=f"open_chat_after_submit_api_{req_id_clean}"):
                        st.session_state["selected_request_id"] = req_id_clean
                        st.switch_page("pages/request_details.py")

                elif resp.status_code == 400:
                    try:
                        msg = resp.json().get("message", "Bad Request")
                    except Exception:
                        msg = resp.text
                    st.error(msg)
                    log_bug("Submit estimate (400)", msg)

                elif resp.status_code in (401, 403):
                    st.error("Not authorized. Please login again.")
                    log_bug("Submit estimate (auth)", resp.text)

                elif resp.status_code == 404:
                    st.error("Request not found.")
                    log_bug("Submit estimate (404)", resp.text)

                else:
                    st.error(f"Server error ({resp.status_code})")
                    log_bug(f"Submit estimate server error {resp.status_code}", resp.text)

            except requests.exceptions.RequestException as ex:
                st.error("Could not connect to backend. Set DATABASE_URL or start the backend at " + CFG.API_BASE)
                log_bug("Submit estimate connection", str(ex))

            except Exception:
                st.error("Unexpected error.")
                log_bug("Submit estimate exception", traceback.format_exc())

st.divider()
_role = get_session_role()
if _role == ROLE_ADMIN:
    if st.button("Back to Admin dashboard"):
        st.switch_page("pages/admin_dashboard.py")
else:
    if st.button("Back to Business portfolio"):
        st.switch_page("pages/business_dashboard.py")

render_footer_bug_panel()