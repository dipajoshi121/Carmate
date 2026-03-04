import os
import traceback
import uuid
from pathlib import Path

import requests
import streamlit as st

from config import CFG

UPLOAD_URL = f"{CFG.API_BASE}/api/service-requests/upload-photos"

st.set_page_config(page_title="Upload Vehicle Photos", page_icon="", layout="centered")

BASE_DIR = Path(__file__).resolve().parent
CSS_PATH = BASE_DIR / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

if "token" not in st.session_state:
    st.warning("Please login first.")
    if st.button("Go to Login"):
        st.switch_page("pages/login.py")
    st.stop()

headers = {
    "Authorization": f"Bearer {st.session_state['token']}"
}

st.title("Upload Vehicle Photos")
st.write("Upload images to support your service request with visual information.")

request_id = st.text_input(
    "Service Request ID",
    placeholder="Enter your request ID"
)

uploaded_files = st.file_uploader(
    "Select vehicle photos",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True
)

if st.button("Upload Photos"):

    if not request_id or not request_id.strip():
        st.error("Service Request ID is required.")
        st.stop()

    if not uploaded_files:
        st.error("Please select at least one photo.")
        st.stop()

    rid = request_id.strip()
    used_db = False

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
                used_db = True
                st.success(f"Photos uploaded successfully! ({added} saved.)")
            else:
                st.error("Could not save photo references to the database.")
        except Exception as e:
            st.error("Database/local save error: " + str(e))

    if not used_db:
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
