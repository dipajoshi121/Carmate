import os
import traceback
from pathlib import Path

import requests
import streamlit as st

from config import CFG
from ui_helpers import (
    require_login,
    auth_headers,
    log_bug,
    render_footer_bug_panel,
    get_session_role,
    ROLE_USER,
    ROLE_BUSINESS,
    ROLE_ADMIN,
)
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

role = get_session_role()
user_id = st.session_state.get("user", {}).get("id") or st.session_state.get("token")

rid = st.session_state.get("selected_request_id")
if not rid:
    st.warning("No request selected. Open a request from your dashboard.")
    if role == ROLE_BUSINESS:
        if st.button("Business portfolio"):
            st.switch_page("pages/business_dashboard.py")
    elif role == ROLE_ADMIN:
        if st.button("Admin dashboard"):
            st.switch_page("pages/admin_dashboard.py")
    else:
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

r = None
used_db = False

if os.environ.get("DATABASE_URL") and user_id:
    try:
        from db import get_request_by_id
        with st.spinner("Loading request..."):
            if role == ROLE_USER:
                row = get_request_by_id(rid, user_id)
            else:
                row = get_request_by_id(rid, None)
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
                "description": row.get("description") or "",
                "ownerUserId": str(row.get("user_id", "")),
                "businessCreatorId": str(row.get("business_creator_id") or ""),
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
            if isinstance(r, dict):
                r.setdefault("ownerUserId", str(r.get("userId") or r.get("user_id") or ""))
                r.setdefault("businessCreatorId", str(r.get("businessCreatorId") or r.get("business_creator_id") or ""))
                r.setdefault("description", r.get("description") or "")
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

bcid = (r.get("businessCreatorId") or "").strip()
owner_uid = (r.get("ownerUserId") or "").strip()
is_customer_owner = role == ROLE_USER and owner_uid and str(owner_uid) == str(user_id)
is_shop_for_request = role == ROLE_BUSINESS and bcid and str(bcid) == str(user_id)
can_submit_estimate = role in (ROLE_BUSINESS, ROLE_ADMIN)
can_edit_request = role == ROLE_ADMIN or (role == ROLE_BUSINESS and bcid and str(bcid) == str(user_id))
can_manage_photos = role == ROLE_ADMIN or is_customer_owner or (role == ROLE_BUSINESS and bcid and str(bcid) == str(user_id))
is_business_participant = is_shop_for_request
if role == ROLE_BUSINESS and not is_business_participant and os.environ.get("DATABASE_URL"):
    try:
        from db import list_request_estimates

        _est_for_access = list_request_estimates(rid)
        is_business_participant = any(str(e.get("business_user_id") or "") == str(user_id) for e in _est_for_access)
    except Exception:
        pass
can_chat = is_customer_owner or is_business_participant
selected_chat_business_id = str(st.session_state.get("selected_chat_business_id") or "").strip()

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
        label = "Your preferred time" if role == ROLE_USER else "Preferred service time"
        st.caption(label + ": " + " at ".join(when_bits))

    if is_customer_owner and status in ("Pending", "Quoted"):
        st.caption("You can cancel this appointment before work has started.")
        if os.environ.get("DATABASE_URL") and user_id:
            if st.button("Cancel appointment", key=f"cancel_appt_{rid}"):
                try:
                    from db import cancel_service_request_by_owner

                    out = cancel_service_request_by_owner(rid, user_id)
                    if out:
                        st.success("Appointment cancelled.")
                        st.rerun()
                    else:
                        st.error("Could not cancel. It may already be in progress or was removed.")
                except Exception as ex:
                    st.error("Database error: " + str(ex))
                    log_bug("cancel appointment", str(ex))

if role == ROLE_BUSINESS:
    st.caption("Submit an estimate from this page or the Submit Estimate page.")
elif role == ROLE_ADMIN:
    st.caption("You can edit this request and override details.")

if can_edit_request and os.environ.get("DATABASE_URL"):
    if (status or "").strip().lower() != "completed":
        if st.button("Mark work as completed", key=f"mark_completed_{rid}"):
            try:
                from db import update_service_request_fields

                out = update_service_request_fields(rid, status="Completed")
                if out:
                    st.success("Job marked as completed.")
                    st.rerun()
                else:
                    st.error("Could not mark this request as completed.")
            except Exception as ex:
                st.error("Database error: " + str(ex))
                log_bug("mark completed", str(ex))
    else:
        st.caption("This request is already marked as completed.")

if can_edit_request and os.environ.get("DATABASE_URL"):
    status_choices = ["Pending", "Quoted", "In Progress", "Completed", "Cancelled"]
    cur_status = status if status in status_choices else status_choices[0]
    st_idx = status_choices.index(cur_status) if cur_status in status_choices else 0
    with st.expander("Edit request (description & status)"):
        with st.form("edit_service_request"):
            new_desc = st.text_area("Description", value=r.get("description") or "", height=100)
            new_status = st.selectbox("Status", status_choices, index=st_idx)
            save_edit = st.form_submit_button("Save changes")
            if save_edit:
                try:
                    from db import update_service_request_fields
                    out = update_service_request_fields(rid, status=new_status, description=new_desc.strip() or None)
                    if out:
                        st.success("Request updated.")
                        st.rerun()
                    else:
                        st.error("Could not update request.")
                except Exception as ex:
                    st.error("Database error: " + str(ex))
                    log_bug("edit request", str(ex))

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
                if os.environ.get("DATABASE_URL") and pid and can_manage_photos:
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

estimate_rows = []
if os.environ.get("DATABASE_URL"):
    try:
        from db import list_request_estimates

        estimate_rows = list_request_estimates(rid)
    except Exception as ex:
        st.caption("Could not load estimate list: " + str(ex))

if estimate_rows:
    st.subheader("Business estimates")
    accepted_estimate = None
    business_rating_cache = {}
    for est in estimate_rows:
        est_id = str(est.get("id", ""))
        est_status = (est.get("status") or "submitted").strip().lower()
        if est_status == "accepted":
            accepted_estimate = est
        business_name = (est.get("business_name") or "").strip() or "Business"
        est_business_uid = str(est.get("business_user_id") or "")
        if str(est.get("business_user_id") or "") == str(user_id):
            business_name += " (you)"
        with st.container(border=True):
            st.markdown(f"**{business_name}** — *{est_status}*")
            if os.environ.get("DATABASE_URL") and est_business_uid:
                if est_business_uid not in business_rating_cache:
                    try:
                        from db import business_rating_summary

                        business_rating_cache[est_business_uid] = business_rating_summary(est_business_uid)
                    except Exception:
                        business_rating_cache[est_business_uid] = None
                bsum = business_rating_cache.get(est_business_uid) or {}
                review_count = int(bsum.get("review_count") or 0)
                avg_rating = bsum.get("avg_rating")
                if review_count > 0 and avg_rating is not None:
                    avg_f = float(avg_rating)
                    stars = min(5, max(1, int(round(avg_f))))
                    st.caption(
                        "Business rating: "
                        + ("★" * stars + "☆" * (5 - stars))
                        + f" ({avg_f:.2f}/5 from {review_count} review(s))"
                    )
                elif is_customer_owner:
                    st.caption("Business rating: No reviews yet.")
            st.dataframe(
                {
                    "Line item": ["Labor", "Parts", "Tax", "Fees", "Total"],
                    f"Amount ({(est.get('currency') or 'USD').upper()})": [
                        est.get("labor") or 0,
                        est.get("parts") or 0,
                        est.get("tax") or 0,
                        est.get("fees") or 0,
                        est.get("total") or 0,
                    ],
                },
                hide_index=True,
                use_container_width=True,
            )
            if est.get("valid_until"):
                st.caption(f"Valid until: {est.get('valid_until')}")
            if est.get("notes"):
                st.caption("Notes: " + str(est.get("notes")))
            if is_customer_owner:
                from db import set_request_estimate_status

                a, b = st.columns(2)
                with a:
                    if st.button("Accept", key=f"accept_est_{est_id}"):
                        if set_request_estimate_status(est_id, "accepted"):
                            st.success("Estimate accepted.")
                            st.rerun()
                        else:
                            st.error("Could not accept this estimate.")
                with b:
                    if st.button("Reject", key=f"reject_est_{est_id}"):
                        if set_request_estimate_status(est_id, "rejected"):
                            st.success("Estimate rejected.")
                            st.rerun()
                        else:
                            st.error("Could not reject this estimate.")
            elif role == ROLE_BUSINESS and str(est.get("business_user_id") or "") == str(user_id):
                req_is_completed = (status or "").strip().lower() == "completed"
                est_is_accepted = est_status == "accepted"
                if est_is_accepted and not req_is_completed:
                    if st.button("Mark work as completed", key=f"mark_completed_from_quote_{rid}_{est_id}"):
                        try:
                            from db import update_service_request_fields

                            out = update_service_request_fields(rid, status="Completed")
                            if out:
                                st.success("Job marked as completed.")
                                st.rerun()
                            else:
                                st.error("Could not mark this request as completed.")
                        except Exception as ex:
                            st.error("Database error: " + str(ex))
                            log_bug("mark completed from quotation", str(ex))
                elif req_is_completed:
                    st.caption("Work already marked as completed.")
    if accepted_estimate and is_customer_owner:
        st.subheader("Payment (PayPal Sandbox)")
        currency = (accepted_estimate.get("currency") or "USD").upper()
        payment_amount = accepted_estimate.get("total")
        try:
            payment_amount = round(float(payment_amount), 2)
        except Exception:
            payment_amount = None
        if payment_amount is None or payment_amount <= 0:
            st.error("Payment amount is invalid. Please ask the business to update estimate values.")
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
            if st.button("Create PayPal Payment Request", key=f"create_pay_{rid}"):
                if not user_id:
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
                        st.error(str(ex))
                        log_bug("Capture payment error", str(ex))
                    except Exception as ex:
                        st.error("Unexpected payment capture error: " + str(ex))
                        log_bug("Capture payment exception", traceback.format_exc())
    elif accepted_estimate and not is_customer_owner:
        st.caption("A customer has accepted one of the estimates.")
else:
    estimate = (r.get("estimate") or {})
    if estimate:
        st.subheader("Cost breakdown & estimate")
        st.caption("Legacy single-estimate view (API mode).")
        currency = estimate.get("currency", "USD")
        labor = estimate.get("labor", 0)
        parts = estimate.get("parts", 0)
        tax = estimate.get("tax", 0)
        fees = estimate.get("fees", 0)
        total = estimate.get("total", None)
        if total is None:
            try:
                total = round(float(labor) + float(parts) + float(tax) + float(fees), 2)
            except Exception:
                total = ""
        st.dataframe(
            {
                "Line item": ["Labor", "Parts", "Tax", "Fees", "Total"],
                f"Amount ({currency})": [labor, parts, tax, fees, total],
            },
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No estimate has been submitted yet.")

if can_chat:
    st.subheader("Customer <-> Business chat")
    st.caption("Messenger-style private 1:1 chats. Each thread is between this customer and one business.")
    if os.environ.get("DATABASE_URL"):
        try:
            from db import (
                list_request_chat_messages,
                add_request_chat_message,
                list_user_chat_conversations,
                mark_request_chat_thread_read,
            )

            thread_business_id = None
            thread_business_name = None
            if is_customer_owner:
                biz_choices = []
                if estimate_rows:
                    for e in estimate_rows:
                        bid = str(e.get("business_user_id") or "")
                        if not bid:
                            continue
                        bname = (e.get("business_name") or "").strip() or "Business"
                        if all(existing_id != bid for existing_id, _ in biz_choices):
                            biz_choices.append((bid, bname))
                if biz_choices:
                    labels = {bid: name for bid, name in biz_choices}
                    if selected_chat_business_id and selected_chat_business_id in labels:
                        default_idx = [bid for bid, _ in biz_choices].index(selected_chat_business_id)
                    else:
                        default_idx = 0
                    thread_business_id = st.selectbox(
                        "Chat with business",
                        options=[bid for bid, _ in biz_choices],
                        index=default_idx,
                        format_func=lambda bid: labels.get(bid, "Business"),
                        key=f"chat_business_pick_{rid}",
                    )
                    thread_business_name = labels.get(thread_business_id)
                    st.session_state["selected_chat_business_id"] = thread_business_id
                else:
                    st.caption("No business quote exists yet, so private chat is unavailable.")
            elif role == ROLE_BUSINESS:
                thread_business_id = str(user_id)
                thread_business_name = "your business"

            if thread_business_id:
                conv_rows = list_user_chat_conversations(user_id, role, limit=200)
                current_thread_key = f"{str(rid)}::{thread_business_id}"
                if not any(f"{str(c.get('request_id'))}::{str(c.get('counterparty_business_user_id'))}" == current_thread_key for c in conv_rows):
                    conv_rows.insert(
                        0,
                        {
                            "request_id": str(rid),
                            "counterparty_business_user_id": thread_business_id,
                            "business_name": thread_business_name or "Business",
                            "customer_name": "Customer",
                            "latest_message": None,
                            "latest_message_at": None,
                            "unread_count": 0,
                        },
                    )

                left, right = st.columns([1, 2], gap="small")
                with left:
                    st.markdown("**Conversations**")
                    for c in conv_rows:
                        c_req = str(c.get("request_id") or "")
                        c_bid = str(c.get("counterparty_business_user_id") or "")
                        if not c_req or not c_bid:
                            continue
                        is_selected = c_req == str(rid) and c_bid == thread_business_id
                        label_name = (
                            (c.get("business_name") if role == ROLE_USER else c.get("customer_name"))
                            or ("Business" if role == ROLE_USER else "Customer")
                        )
                        latest = (c.get("latest_message") or "").strip()
                        unread_count = int(c.get("unread_count") or 0)
                        button_label = f"{label_name} | Req {c_req[:8]}"
                        if unread_count > 0:
                            button_label += f" ({unread_count})"
                        if st.button(
                            button_label,
                            key=f"conv_pick_{c_req}_{c_bid}",
                            type="primary" if is_selected else "secondary",
                            use_container_width=True,
                        ):
                            st.session_state["selected_request_id"] = c_req
                            st.session_state["selected_chat_business_id"] = c_bid
                            st.rerun()

                msgs = list_request_chat_messages(
                    rid,
                    limit=200,
                    viewer_user_id=user_id,
                    viewer_role=role,
                    counterparty_business_user_id=thread_business_id,
                )
                _ = mark_request_chat_thread_read(
                    request_id=rid,
                    counterparty_business_user_id=thread_business_id,
                    viewer_user_id=user_id,
                    viewer_role=role,
                )

                with right:
                    if thread_business_name:
                        st.markdown(f"**Chat with {thread_business_name}**")
                    if msgs:
                        for m in msgs:
                            msg_sender = str(m.get("sender_user_id") or "")
                            mine = msg_sender == str(user_id)
                            msg_name = (m.get("sender_name") or "").strip() or ("You" if mine else "Other")
                            created_at = m.get("created_at")
                            created_s = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at) if created_at else ""
                            bubble = "> " + str(m.get("message") or "").strip()
                            if mine:
                                st.markdown(
                                    "<div style='text-align:right'><b>You</b></div>",
                                    unsafe_allow_html=True,
                                )
                                st.info(bubble)
                            else:
                                st.markdown(f"**{msg_name}**")
                                st.write(str(m.get("message") or ""))
                            if created_s:
                                st.caption(created_s)
                    else:
                        st.caption("No messages yet.")

                    with st.form(f"chat_form_{rid}_{thread_business_id}", clear_on_submit=True):
                        new_msg = st.text_area("Message", placeholder="Type your message...", height=100)
                        send_msg = st.form_submit_button("Send")
                        if send_msg:
                            sender_label = (
                                (st.session_state.get("user", {}) or {}).get("fullName")
                                or (st.session_state.get("user", {}) or {}).get("full_name")
                                or (st.session_state.get("user", {}) or {}).get("email")
                                or role.title()
                            )
                            out = add_request_chat_message(
                                request_id=rid,
                                sender_user_id=user_id,
                                sender_role=role,
                                sender_name=sender_label,
                                message=new_msg,
                                counterparty_business_user_id=thread_business_id,
                            )
                            if out:
                                st.success("Message sent.")
                                st.rerun()
                            else:
                                st.error("Could not send message. Only this customer and the selected quoted business can use this thread.")
        except Exception as ex:
            st.caption("Chat requires database access: " + str(ex))
            log_bug("request details chat", traceback.format_exc())
    else:
        st.caption("Chat is available when DATABASE_URL is configured.")
elif role in (ROLE_USER, ROLE_BUSINESS):
    st.caption("Private chat is only available to the request owner and the assigned business.")

if os.environ.get("DATABASE_URL") and user_id:
    try:
        from db import (
            create_review_report,
            get_review_for_request,
            set_provider_review_response,
            upsert_request_review,
        )

        review_row = get_review_for_request(rid)
        is_completed = (status or "").strip() == "Completed"

        st.subheader("Reviews & ratings")

        if review_row:
            rt = int(review_row.get("rating") or 0)
            st.markdown("**" + "★" * rt + "☆" * max(0, 5 - rt) + f"** ({rt}/5)")
            if review_row.get("comment"):
                st.write(review_row.get("comment"))
            if review_row.get("provider_response"):
                st.info("**Provider reply:** " + str(review_row.get("provider_response")))

            rev_id = str(review_row.get("id"))
            if str(review_row.get("reviewer_user_id")) != str(user_id):
                with st.expander("Report this review"):
                    rreason = st.text_area("Reason", key=f"report_reason_{rid}", placeholder="Why should this be reviewed?")
                    if st.button("Submit report", key=f"report_submit_{rid}"):
                        res = create_review_report(rev_id, user_id, rreason)
                        if res:
                            st.success("Report submitted. An administrator will review it.")
                            st.rerun()
                        else:
                            st.error("Could not submit report.")

        if is_completed and is_customer_owner:
            st.caption("Share feedback on your completed service.")
            prev_r = int(review_row.get("rating") or 5) if review_row else 5
            prev_c = (review_row.get("comment") or "") if review_row else ""
            with st.form("customer_review_form"):
                stars = st.slider("Rating", 1, 5, prev_r, key=f"rv_st_{rid}")
                cmt = st.text_area("Comments", value=prev_c, key=f"rv_cmt_{rid}")
                submitted_rv = st.form_submit_button("Submit review" if not review_row else "Update review")
                if submitted_rv:
                    out = upsert_request_review(rid, user_id, stars, cmt)
                    if out:
                        st.success("Thank you — your review was saved.")
                        st.rerun()
                    else:
                        st.error("Could not save review.")

        if review_row and is_shop_for_request:
            with st.form("provider_feedback_form"):
                st.caption("Public reply visible to the customer.")
                pf = st.text_area(
                    "Provider feedback",
                    value=review_row.get("provider_response") or "",
                    key=f"pf_{rid}",
                    height=100,
                )
                if st.form_submit_button("Save provider reply"):
                    out = set_provider_review_response(rid, user_id, pf)
                    if out:
                        st.success("Reply saved.")
                        st.rerun()
                    else:
                        st.error("Could not save reply. Check that your shop is assigned to this request.")

        if not review_row and not (is_completed and is_customer_owner):
            st.caption(
                "Customer reviews appear here after the job is marked **Completed**. "
                "Anyone can browse shop averages under **View ratings** in the menu."
            )
    except Exception as ex:
        st.caption("Reviews require database access: " + str(ex))
        log_bug("request details reviews", traceback.format_exc())

st.divider()
if role == ROLE_USER:
    if st.button("Back to My Requests"):
        st.switch_page("pages/my_request.py")
elif role == ROLE_BUSINESS:
    if st.button("Back to Business portfolio"):
        st.switch_page("pages/business_dashboard.py")
else:
    if st.button("Back to Admin dashboard"):
        st.switch_page("pages/admin_dashboard.py")
if can_submit_estimate:
    if st.button("Submit Estimate for this request"):
        st.session_state["selected_request_id"] = rid
        st.switch_page("pages/submit_estimate.py")

render_footer_bug_panel()
