import os
import traceback
from pathlib import Path

import requests
import streamlit as st

from config import CFG
from ui_helpers import require_login, auth_headers, log_bug, render_footer_bug_panel
from payments import create_payment_request_api, capture_paypal_order, PaymentError

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

friendly_labels = st.session_state.get("request_labels") or {}
friendly_name = friendly_labels.get(str(rid))

st.title("Request Details")
if friendly_name:
    st.caption(f"{friendly_name} (ID: {rid})")
else:
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
            preferred_date = row.get("preferred_date")
            preferred_time = row.get("preferred_time")
            estimate = row.get("estimate") or {}
            r = {
                "id": str(row.get("id", "")),
                "vehicle": row.get("vehicle") or {},
                "serviceType": row.get("service_type") or "Service",
                "status": row.get("status") or "Pending",
                "createdAt": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at) if created_at else "",
                "preferredDate": preferred_date.isoformat() if hasattr(preferred_date, "isoformat") else str(preferred_date) if preferred_date else "",
                "preferredTime": preferred_time.strftime("%H:%M") if hasattr(preferred_time, "strftime") else str(preferred_time) if preferred_time else "",
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
preferred_date_str = r.get("preferredDate") or ""
preferred_time_str = r.get("preferredTime") or ""

with st.container(border=True):
    st.subheader("Request summary")
    st.markdown(f"**{service_type}** — *{status}*")
    st.write(title if title else "Vehicle info not available")
    if created:
        st.caption(f"Created: {created}")
    if preferred_date_str or preferred_time_str:
        when_bits = []
        if preferred_date_str:
            when_bits.append(preferred_date_str)
        if preferred_time_str:
            when_bits.append(preferred_time_str)
        st.caption("Customer preferred time: " + " at ".join(when_bits))

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
            pid = photo.get("id")
            fp = photo.get("file_path")
            if not fp:
                continue
            abs_path = PROJECT_ROOT / fp
            with cols[idx % len(cols)]:
                if abs_path.exists():
                    try:
                        st.image(str(abs_path), use_container_width=True)
                    except Exception:
                        st.caption("Photo")
                if os.environ.get("DATABASE_URL") and pid:
                    if st.button("Delete Photo", key=f"del_photo_{pid}"):
                        deleted = False
                        err = None
                        try:
                            from db import delete_request_photo
                            if delete_request_photo(pid, rid):
                                deleted = True
                                try:
                                    if abs_path.exists():
                                        abs_path.unlink()
                                except Exception:
                                    pass
                            else:
                                err = "Could not delete photo in the database."
                        except Exception as ex:
                            err = "Database error: " + str(ex)
                        if deleted:
                            st.success("Photo deleted.")
                            st.rerun()
                        elif err:
                            st.error(err)
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
        elif est_status == "accepted":
            st.subheader("Payment (PayPal Sandbox)")
            payment_amount = total
            try:
                payment_amount = round(float(payment_amount), 2)
            except Exception:
                payment_amount = None

            if payment_amount is None or payment_amount <= 0:
                st.error("Payment amount is invalid. Please update the estimate total.")
            else:
                latest_payment = None
                if os.environ.get("DATABASE_URL"):
                    try:
                        from db import get_latest_payment_for_request
                        latest_payment = get_latest_payment_for_request(rid)
                    except Exception as ex:
                        st.error("Database error while loading payment history: " + str(ex))

                if latest_payment:
                    st.caption(
                        f"Latest payment status: {latest_payment.get('status')} | "
                        f"Order: {latest_payment.get('paypal_order_id') or '-'}"
                    )
                    if latest_payment.get("failure_reason"):
                        st.caption("Failure reason: " + str(latest_payment.get("failure_reason")))

                if st.button("Create PayPal Payment Request", key=f"create_pay_{rid}"):
                    if not os.environ.get("DATABASE_URL"):
                        st.error("DATABASE_URL is required so transactions can be stored.")
                    elif not user_id:
                        st.error("Missing user session. Please login again.")
                    else:
                        try:
                            payment_request = create_payment_request_api(
                                request_id=rid,
                                user_id=user_id,
                                amount=payment_amount,
                                currency=currency,
                                description=f"Carmate request {rid}",
                            )
                            st.success("Payment request created.")
                            approve_url = payment_request.get("approve_url")
                            if approve_url:
                                st.markdown(f"[Approve payment in PayPal Sandbox]({approve_url})")
                            st.session_state[f"payment_order_id_{rid}"] = payment_request.get("order_id")
                        except PaymentError as ex:
                            st.error(str(ex))
                            log_bug("Create payment request error", str(ex))
                        except Exception as ex:
                            st.error("Unexpected payment error: " + str(ex))
                            log_bug("Create payment request exception", traceback.format_exc())

                default_order_id = st.session_state.get(f"payment_order_id_{rid}", "")
                if not default_order_id and latest_payment:
                    default_order_id = latest_payment.get("paypal_order_id") or ""
                capture_order_id = st.text_input("PayPal Order ID to capture", value=default_order_id, key=f"capture_order_{rid}")

                if st.button("Capture Payment", key=f"capture_pay_{rid}"):
                    if not capture_order_id.strip():
                        st.error("Order ID is required.")
                    elif not os.environ.get("DATABASE_URL"):
                        st.error("DATABASE_URL is required so transactions can be stored.")
                    else:
                        try:
                            capture = capture_paypal_order(capture_order_id.strip())
                            from db import update_payment_transaction_by_order
                            update_payment_transaction_by_order(
                                paypal_order_id=capture_order_id.strip(),
                                status=(capture.get("status") or "completed").lower(),
                                paypal_capture_id=capture.get("capture_id"),
                                raw_response=capture.get("raw"),
                            )
                            st.success("Payment captured successfully.")
                        except PaymentError as ex:
                            try:
                                from db import update_payment_transaction_by_order
                                update_payment_transaction_by_order(
                                    paypal_order_id=capture_order_id.strip(),
                                    status="failed",
                                    failure_reason=str(ex),
                                )
                            except Exception:
                                pass
                            st.error(str(ex))
                            log_bug("Capture payment error", str(ex))
                        except Exception as ex:
                            st.error("Unexpected payment capture error: " + str(ex))
                            log_bug("Capture payment exception", traceback.format_exc())
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
