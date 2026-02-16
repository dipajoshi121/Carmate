import requests
import streamlit as st
from pathlib import Path
import traceback

# ---------------- CONFIG ----------------
API_BASE = "http://localhost:8501"
UPLOAD_URL = f"{API_BASE}/api/service-requests/upload-photos"

st.set_page_config(
    page_title="Upload Vehicle Photos",
    page_icon="📸",
    layout="centered"
)

# ---------------- AUTH CHECK ----------------
if "token" not in st.session_state:
    st.warning("Please login first.")
    if st.button("Go to Login"):
        st.switch_page("pages/login.py")
    st.stop()

headers = {
    "Authorization": f"Bearer {st.session_state['token']}"
}

# ---------------- UI ----------------
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

    if not request_id:
        st.error("Service Request ID is required.")
        st.stop()

    if not uploaded_files:
        st.error("Please select at least one photo.")
        st.stop()

    try:
        files = []

        for file in uploaded_files:
            files.append(
                ("photos", (file.name, file.getvalue(), file.type))
            )

        data = {
            "requestId": request_id
        }

        with st.spinner("Uploading photos..."):
            response = requests.post(
                UPLOAD_URL,
                headers=headers,
                data=data,
                files=files,
                timeout=30
            )

        if response.status_code in (200, 201):
            st.success("✅ Photos uploaded successfully!")
            st.json(response.json())

        elif response.status_code == 400:
            st.error("❌ Invalid request.")
            st.text(response.text)

        elif response.status_code in (401, 403):
            st.error("❌ Unauthorized. Please login again.")

        else:
            st.error(f"❌ Server error: {response.status_code}")
            st.text(response.text)

    except Exception:
        st.error("Unexpected error occurred.")
        st.text(traceback.format_exc())
