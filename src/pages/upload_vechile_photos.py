import os
import traceback
import uuid
from pathlib import Path

import requests
import streamlit as st

from config import CFG
from ui_helpers import auth_headers, require_login, log_bug

UPLOAD_URL = f"{CFG.API_BASE}/api/service-requests/upload-photos"
MY_REQUESTS_URL = f"{CFG.API_BASE}/api/service-requests/me"

st.set_page_config(page_title="Upload Vehicle Photos", page_icon="", layout="centered")

BASE_DIR = Path(__file__).resolve().parent
CSS_PATH = BASE_DIR / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

require_login()

st.title("Upload Vehicle Photos")
st.write("Upload images to support your service request with visual information.")

user_id = st.session_state.get("user", {}).get("id") or st.session_state.get("token")
headers = auth_headers()

requests_list = []
used_db = False

if os.environ.get("DATABASE_URL") and user_id:
    try:
        from db import get_my_requests, DatabaseError
        with st.spinner("Loading your requests..."):
            raw = get_my_requests(user_id)
        for idx, r in enumerate(raw, start=1):
            rid = str(r.get("id"))
            vehicle = r.get("vehicle") or {}
            title = f"{vehicle.get('year','')} {vehicle.get('make','')} {vehicle.get('model','')}".strip()
            label = f"Request {idx}" + (f" – {title}" if title else "")
            requests_list.append({"id": rid, "label": label})
        used_db = True
    except DatabaseError as e:
        st.error("Database error while loading requests: " + str(e))
        log_bug("Upload photos DB error", str(e))
        used_db = False
    except Exception:
        st.error("Could not load your requests from the database.")
        log_bug("Upload photos DB error", traceback.format_exc())
        used_db = False

if not used_db:
    try:
        with st.spinner("Loading your requests..."):
            resp = requests.get(MY_REQUESTS_URL, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json() if "application/json" in resp.headers.get("content-type", "") else []
            for idx, r in enumerate(data, start=1):
                rid = str(r.get("id") or r.get("_id") or "")
                vehicle = r.get("vehicle") or {}
                title = f"{vehicle.get('year','')} {vehicle.get('make','')} {vehicle.get('model','')}".strip()
                label = f"Request {idx}" + (f" – {title}" if title else "")
                requests_list.append({"id": rid, "label": label})
        elif resp.status_code in (401, 403):
            st.error("Session expired. Please login again.")
        else:
            st.error(f"Could not load your requests ({resp.status_code}).")
    except requests.exceptions.RequestException as ex:
        st.error("Could not connect to backend to load requests. Start the backend at " + CFG.API_BASE)
    except Exception:
        st.error("Unexpected error while loading requests.")
        st.text(traceback.format_exc())

if not requests_list:
    st.info("You do not have any requests yet. Please create a service request first.")
    if st.button("Create a Request"):
        st.switch_page("pages/service_request.py")
    st.stop()

labels = [r["label"] for r in requests_list]
indices = list(range(len(labels)))

selected_index = st.selectbox(
    "Select the service request to attach photos to",
    indices,
    format_func=lambda i: labels[i],
)

selected_request_id = requests_list[selected_index]["id"]

uploaded_files = st.file_uploader(
    "Select vehicle photos",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
)

if st.button("Upload Photos"):

    if not uploaded_files:
        st.error("Please select at least one photo.")
        st.stop()

    rid = selected_request_id
    used_db_upload = False

    if os.environ.get("DATABASE_URL"):
        try:
            from db import add_request_photo
            uploads_root = Path(__file__).resolve().parent.parent.parent / "uploads"
            request_dir = uploads_root / rid
            request_dir.mkdir(parents=True, exist_ok=True)
            added = 0
            with st.spinner("Uploading photos..."):
                for file in uploaded_files:
                    safe_name = f"{uuid.uuid4().hex}_{file.name}"
                    dest = request_dir / safe_name
                    dest.write_bytes(file.getvalue())
                    rel_path = f"uploads/{rid}/{safe_name}"
                    if add_request_photo(rid, rel_path):
                        added += 1
            if added > 0:
                used_db_upload = True
                st.success(f"Photos uploaded successfully! ({added} saved.)")
            else:
                st.error("Could not save photo references to the database.")
        except Exception as e:
            st.error("Database/local save error: " + str(e))

    if not used_db_upload:
        try:
            files = []
            for file in uploaded_files:
                files.append(("photos", (file.name, file.getvalue(), file.type)))
            data = {"requestId": rid}
            with st.spinner("Uploading photos..."):
                response = requests.post(
                    UPLOAD_URL,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=30,
                )

            if response.status_code in (200, 201):
                st.success("Photos uploaded successfully!")
                st.json(response.json())

            elif response.status_code == 400:
                st.error("Invalid request.")
                st.text(response.text)

            elif response.status_code in (401, 403):
                st.error("Unauthorized. Please login again.")

            else:
                st.error(f"Server error: {response.status_code}")
                st.text(response.text)

        except requests.exceptions.RequestException as ex:
            st.error("Could not connect to backend. Set DATABASE_URL or start the backend at " + CFG.API_BASE)

        except Exception:
            st.error("Unexpected error occurred.")
            st.text(traceback.format_exc())

st.divider()
if st.button("Back to My Requests"):
    st.switch_page("pages/my_request.py")
