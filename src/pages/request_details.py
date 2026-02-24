
import requests
import streamlit as st

from config import CFG
from ui_helpers import auth_headers, log_bug

UPDATE_ESTIMATE_STATUS_URL = f"{CFG.API_BASE}/api/service-requests/{{}}/estimate/status"

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

    # If backend didn't store total, compute it safely
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

        # Only allow accept/reject if it is still waiting
        if est_status in ("submitted", "pending", "quoted"):
            colA, colB = st.columns(2)

            with colA:
                if st.button("✅ Accept Estimate", key=f"accept_est_{rid}"):
                    try:
                        resp = requests.patch(
                            UPDATE_ESTIMATE_STATUS_URL.format(rid),
                            json={"status": "accepted"},
                            headers={**auth_headers(), "Content-Type": "application/json"},
                            timeout=20,
                        )
                        if resp.status_code in (200, 201):
                            st.success("Estimate accepted.")
                            st.experimental_rerun()
                        else:
                            st.error(f"Could not accept estimate ({resp.status_code})")
                            log_bug("Accept estimate error", resp.text)
                    except Exception as ex:
                        st.error("Error contacting server.")
                        log_bug("Accept estimate exception", str(ex))

            with colB:
                if st.button("❌ Reject Estimate", key=f"reject_est_{rid}"):
                    try:
                        resp = requests.patch(
                            UPDATE_ESTIMATE_STATUS_URL.format(rid),
                            json={"status": "rejected"},
                            headers={**auth_headers(), "Content-Type": "application/json"},
                            timeout=20,
                        )
                        if resp.status_code in (200, 201):
                            st.success("Estimate rejected.")
                            st.experimental_rerun()
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