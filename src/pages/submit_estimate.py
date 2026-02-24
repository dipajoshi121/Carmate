

import traceback
from datetime import date, timedelta
from pathlib import Path

import requests
import streamlit as st

from config import CFG
from ui_helpers import require_login, auth_headers, log_bug, render_footer_bug_panel

# ------------------ API ------------------
SUBMIT_ESTIMATE_URL = f"{CFG.API_BASE}/api/service-requests/{{}}/estimate"

# ------------------ PAGE ------------------
st.set_page_config(page_title="Carmate - Submit Estimate", page_icon="🧾", layout="centered")

# ------------------ LOAD CSS (optional) ------------------
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
CSS_PATH = PROJECT_ROOT / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

# ------------------ AUTH ------------------
require_login()

# ------------------ UI ------------------
st.title("Submit Estimate")
st.write("Submit an estimated cost so the customer knows the expected service cost.")

# Optional: prefill request_id if navigated from another page
prefill_rid = st.session_state.get("selected_request_id", "")
request_id = st.text_input("Service Request ID", value=prefill_rid, placeholder="Paste the request ID here")

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

# Live preview total (outside form so it updates instantly)
total = round(float(labor) + float(parts) + float(tax) + float(fees), 2)
st.caption(f"Estimated Total: {currency.strip().upper()} {total}")

if submitted:
    if not request_id or not request_id.strip():
        st.error("Service Request ID is required.")
    else:
        payload = {
            "currency": currency.strip().upper(),
            "labor": float(labor),
            "parts": float(parts),
            "tax": float(tax),
            "fees": float(fees),
            "total": total,  # include total for convenience; backend can recompute too
            "notes": notes.strip(),
            "valid_until": valid_until.isoformat() if valid_until else None,
            "status": "submitted",
        }

        try:
            with st.spinner("Submitting estimate..."):
                resp = requests.patch(
                    SUBMIT_ESTIMATE_URL.format(request_id.strip()),
                    json=payload,
                    headers={**auth_headers(), "Content-Type": "application/json"},
                    timeout=20,
                )

            if resp.status_code in (200, 201):
                st.success("✅ Estimate submitted successfully!")
                if "application/json" in resp.headers.get("content-type", ""):
                    st.json(resp.json())
                else:
                    st.text(resp.text)

            elif resp.status_code == 400:
                try:
                    msg = resp.json().get("message", "Bad Request")
                except Exception:
                    msg = resp.text
                st.error(f"❌ {msg}")
                log_bug("Submit estimate (400)", msg)

            elif resp.status_code in (401, 403):
                st.error("❌ Not authorized. Please login again.")
                log_bug("Submit estimate (auth)", resp.text)

            elif resp.status_code == 404:
                st.error("❌ Request not found.")
                log_bug("Submit estimate (404)", resp.text)

            else:
                st.error(f"❌ Server error ({resp.status_code})")
                log_bug(f"Submit estimate server error {resp.status_code}", resp.text)

        except requests.exceptions.RequestException as ex:
            st.error("❌ Could not connect to backend API.")
            log_bug("Submit estimate connection", str(ex))

        except Exception:
            st.error("❌ Unexpected error.")
            log_bug("Submit estimate exception", traceback.format_exc())

st.divider()
if st.button("Back to My Requests"):
    st.switch_page("pages/my_requests.py")

render_footer_bug_panel()