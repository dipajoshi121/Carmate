import streamlit as st
import requests
import time
import traceback

# ------------------ API (BACKEND) ------------------
API_BASE = "http://localhost:8501"  # Replace with your backend API base URL
FORGOT_URL = f"{API_BASE}/api/auth/forgot-password"  # Password reset endpoint

# ------------------ PAGE ------------------
st.set_page_config(page_title="Carmate - Forgot Password", page_icon="🛻", layout="centered")

# ------------------ UI ------------------
st.title("Forgot Password")
st.write("Enter your email address and we'll send you instructions to reset your password.")

# Form to input email
with st.form("forgot_password_form", clear_on_submit=False):
    fp_email = st.text_input("Email for reset", key="fp_email", placeholder="e.g., arjun@example.com")
    send_btn = st.form_submit_button("Send reset link")

# ------------------ HANDLE PASSWORD RESET REQUEST ------------------
if send_btn:
    # Validate email format
    if not fp_email or not is_valid_email(fp_email):
        st.error("Please enter a valid email address.")
    else:
        # Send reset request to the backend
        try:
            with st.spinner("Sending reset request..."):
                response = requests.post(FORGOT_URL, json={"email": fp_email.strip().lower()}, timeout=10)

            if response.status_code in (200, 201, 202):
                st.success("✅ If that email exists, reset instructions were sent.")
            else:
                st.error(f"❌ Request failed ({response.status_code})")
                log_bug("Forgot password API error", response.text)

        except requests.exceptions.RequestException as ex:
            st.error("❌ Could not connect to the backend API.")
            log_bug("Forgot password connection error", str(ex))
        except Exception as e:
            st.error("❌ Unexpected error.")
            log_bug("Forgot password exception", traceback.format_exc())

# ------------------ EMAIL VALIDATION ------------------
def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", (email or "").strip()))

# ------------------ LOGGING ERRORS ------------------
if "error_log" not in st.session_state:
    st.session_state.error_log = []

def log_bug(title: str, details: str = ""):
    st.session_state.error_log.append({
        "time": time.strftime("%H:%M:%S"),
        "title": title,
        "details": details
    })
