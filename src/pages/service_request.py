# pages/service_request.py

import re
import traceback
from datetime import date, timedelta
from pathlib import Path

import requests
import streamlit as st

from config import CFG
from ui_helpers import log_bug, render_footer_bug_panel, require_login, auth_headers

# ------------------ API ------------------
CREATE_REQUEST_URL = f"{CFG.API_BASE}/api/service-requests"

# ------------------ PAGE ------------------
st.set_page_config(page_title="Carmate - Create Service Request", page_icon="🛠️", layout="centered")

# ------------------ LOAD CSS (optional) ------------------
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent  # if /pages/, parent is project root
CSS_PATH = PROJECT_ROOT / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

# ------------------ AUTH ------------------
require_login()

# ------------------ VALIDATORS ------------------
def valid_year(y: int) -> bool:
    return 1980 <= y <= (date.today().year + 1)

def valid_vin(v: str) -> bool:
    v = (v or "").strip().upper()
    if not v:
        return True  # optional
    return bool(re.match(r"^[A-HJ-NPR-Z0-9]{11,17}$", v))  # excludes I,O,Q

# ------------------ UI ------------------
st.title("Create Service Request")
st.write("Tell us about your car and what service you need. We’ll route it to the right shop/technician.")

with st.form("service_request_form", clear_on_submit=False):
    st.subheader("Vehicle Info")

    col1, col2 = st.columns(2)
    with col1:
        make = st.text_input("Make", placeholder="e.g., Toyota")
        model = st.text_input("Model", placeholder="e.g., Camry")
        year = st.number_input("Year", min_value=1980, max_value=date.today().year + 1, value=date.today().year, step=1)
    with col2:
        plate = st.text_input("License Plate (optional)", placeholder="e.g., ABC-1234")
        vin = st.text_input("VIN (optional)", placeholder="17-char VIN")
        mileage = st.number_input("Mileage (optional)", min_value=0, max_value=999999, value=0, step=100)

    st.subheader("Service Details")

    service_type = st.selectbox(
        "Service Type",
        [
            "Oil Change",
            "Brake Service",
            "Tire / Alignment",
            "Battery / Electrical",
            "Engine / Check Light",
            "AC / Heating",
            "Inspection",
            "Other",
        ],
        index=0,
    )

    symptoms = st.text_area(
        "Symptoms / Problem Description",
        placeholder="Example: Car makes a squealing sound when braking; check engine light came on yesterday.",
        height=120,
    )

    col3, col4 = st.columns(2)
    with col3:
        preferred_date = st.date_input("Preferred Date", value=date.today() + timedelta(days=1), min_value=date.today())
    with col4:
        preferred_time = st.selectbox("Preferred Time Window", ["Morning", "Afternoon", "Evening", "Flexible"], index=3)

    location = st.text_input("Service Location (City/Area)", placeholder="e.g., Commerce, TX")
    urgency = st.select_slider("Urgency", options=["Low", "Medium", "High"], value="Medium")

    st.subheader("Optional Uploads")
    photos = st.file_uploader(
        "Upload photos (dash warning, damage, parts, etc.)",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
    )

    submitted = st.form_submit_button("Submit Service Request")

if submitted:
    errors = []
    if not make or len(make.strip()) < 2:
        errors.append("Make is required.")
    if not model or len(model.strip()) < 1:
        errors.append("Model is required.")
    if not valid_year(int(year)):
        errors.append("Year looks invalid.")
    if not symptoms or len(symptoms.strip()) < 10:
        errors.append("Please describe the issue (at least ~10 characters).")
    if not location or len(location.strip()) < 2:
        errors.append("Location is required.")
    if not valid_vin(vin):
        errors.append("VIN format looks invalid (optional field, but if filled it must be valid).")

    if errors:
        st.error(" | ".join(errors))
        log_bug("Service request validation", " | ".join(errors))
    else:
        payload = {
            "vehicle": {
                "make": make.strip(),
                "model": model.strip(),
                "year": int(year),
                "licensePlate": plate.strip() if plate else "",
                "vin": vin.strip().upper() if vin else "",
                "mileage": int(mileage) if mileage else 0,
            },
            "serviceType": service_type,
            "symptoms": symptoms.strip(),
            "preferredDate": preferred_date.isoformat(),
            "preferredTimeWindow": preferred_time,
            "location": location.strip(),
            "urgency": urgency,
        }

        try:
            # If your backend supports multipart uploads, we can send files too.
            # Here we do:
            # - JSON request if no photos
            # - multipart/form-data if photos exist
            with st.spinner("Submitting..."):
                if photos:
                    files = []
                    for f in photos:
                        files.append(("photos", (f.name, f.getvalue(), f.type)))
                    resp = requests.post(
                        CREATE_REQUEST_URL,
                        data={"payload": str(payload)},   # backend can parse payload string OR you change to JSON
                        files=files,
                        headers=auth_headers(),
                        timeout=20,
                    )
                else:
                    resp = requests.post(
                        CREATE_REQUEST_URL,
                        json=payload,
                        headers={**auth_headers(), "Content-Type": "application/json"},
                        timeout=20,
                    )

            if resp.status_code in (200, 201):
                data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
                st.success("✅ Service request created!")
                if data:
                    st.json(data)
                st.divider()
                if st.button("View My Requests"):
                    st.switch_page("pages/my_requests.py")
            elif resp.status_code == 400:
                try:
                    msg = resp.json().get("message", "Bad Request")
                except Exception:
                    msg = resp.text
                st.error(f"❌ {msg}")
                log_bug("Create request (400)", msg)
            elif resp.status_code in (401, 403):
                st.error("❌ You are not authorized. Please login again.")
                log_bug("Create request (auth)", resp.text)
            else:
                st.error(f"❌ Server error ({resp.status_code})")
                log_bug(f"Create request server error {resp.status_code}", resp.text)

        except requests.exceptions.RequestException as ex:
            st.error("❌ Could not connect to backend API.")
            log_bug("Create request connection error", str(ex))
        except Exception:
            st.error("❌ Unexpected error.")
            log_bug("Create request exception", traceback.format_exc())

render_footer_bug_panel()
