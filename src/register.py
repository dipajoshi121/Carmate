import re
import time
import traceback
import requests
import streamlit as st

API_BASE = "http://localhost:8501"
REGISTER_URL = f"{API_BASE}/api/auth/register"

st.set_page_config(page_title="Carmate - Register", page_icon="🚗", layout="centered")

# ---------- Error Log in session ----------
if "error_log" not in st.session_state:
    st.session_state.error_log = []

def log_error(title: str, details: str = ""):
    st.session_state.error_log.append({
        "time": time.strftime("%H:%M:%S"),
        "title": title,
        "details": details
    })

# ---------- Validators ----------
def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", (email or "").strip()))

def is_valid_phone(phone: str) -> bool:
    digits = re.sub(r"[^\d]", "", phone or "")
    return 7 <= len(digits) <= 15

def password_policy(password: str):
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", password):
        return False, "Password must include at least one letter."
    if not re.search(r"\d", password):
        return False, "Password must include at least one number."
    return True, ""

# ---------- UI ----------
st.title("🚗 Carmate - User Account Registration")
st.write("Create an account to access Carmate services.")

with st.form("register_form", clear_on_submit=False):
    full_name = st.text_input("Full Name", placeholder="e.g., Arjun Khatri")
    email = st.text_input("Email", placeholder="e.g., arjun@example.com")
    phone = st.text_input("Phone Number", placeholder="e.g., +1 555-555-5555")
    password = st.text_input("Password", type="password", placeholder="Min 8 chars, letters + numbers")
    confirm_password = st.text_input("Confirm Password", type="password")
    role = st.selectbox("Role", options=["customer", "provider"], index=0)

    submitted = st.form_submit_button("Create Account")

if submitted:
    # ---------- Client-side validation ----------
    errors = []

    if not full_name or len(full_name.strip()) < 2:
        errors.append("Full name is required (at least 2 characters).")
    if not is_valid_email(email):
        errors.append("Please enter a valid email address.")
    if not is_valid_phone(phone):
        errors.append("Please enter a valid phone number (7–15 digits).")

    ok, reason = password_policy(password)
    if not ok:
        errors.append(reason)

    if password != confirm_password:
        errors.append("Passwords do not match.")

    if errors:
        msg = " | ".join(errors)
        st.error("Please fix the form errors above.")
        log_error("Form validation failed", msg)

    else:
        payload = {
            "fullName": full_name.strip(),
            "email": email.strip().lower(),
            "phone": phone.strip(),
            "password": password,
            "role": role
        }

        try:
            with st.spinner("Creating your account..."):
                resp = requests.post(REGISTER_URL, json=payload, timeout=10)

            if resp.status_code == 201:
                data = resp.json()
                st.success("✅ Registration successful!")
                st.json({
                    "id": data["user"]["id"],
                    "fullName": data["user"]["fullName"],
                    "email": data["user"]["email"],
                    "phone": data["user"]["phone"],
                    "role": data["user"]["role"],
                    "isActive": data["user"]["isActive"]
                })

            elif resp.status_code == 409:
                st.warning("⚠️ This email is already registered. Try logging in.")
                log_error("Duplicate email (409)", resp.text)

            elif resp.status_code == 400:
                # backend validation message
                try:
                    backend_msg = resp.json().get("message", "Bad Request")
                except Exception:
                    backend_msg = resp.text
                st.error(f"❌ Validation error: {backend_msg}")
                log_error("Backend validation error (400)", backend_msg)

            else:
                st.error(f"❌ Server error ({resp.status_code})")
                log_error(f"Unexpected server status {resp.status_code}", resp.text)

        except requests.exceptions.RequestException as ex:
            st.error("❌ Could not connect to backend API.")
            log_error("Backend connection error", str(ex))

        except Exception as ex:
            st.error("❌ Unexpected frontend error.")
            log_error("Frontend exception", f"{ex}\n\n{traceback.format_exc()}")

# ---------- Sticky Footer Debug Panel ----------
st.markdown(
    """
    <style>
      .debug-footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background: rgba(10,10,10,0.92);
        color: #fff;
        padding: 10px 16px;
        font-size: 13px;
        border-top: 1px solid rgba(255,255,255,0.15);
        z-index: 9999;
      }
      .debug-footer details summary {
        cursor: pointer;
        font-weight: 600;
      }
      .debug-item {
        margin-top: 6px;
        padding-top: 6px;
        border-top: 1px dashed rgba(255,255,255,0.2);
        white-space: pre-wrap;
      }
      .debug-muted { opacity: 0.8; }
    </style>
    """,
    unsafe_allow_html=True
)

# Prepare footer contents
log = st.session_state.error_log[-5:]  # show last 5 errors
count = len(st.session_state.error_log)

footer_html = f"""
<div class="debug-footer">
  <details {'open' if count > 0 else ''}>
    <summary>🐞 Debug Footer — {count} issue(s) logged (showing last {min(5,count)})</summary>
    <div class="debug-muted">This panel helps you report bugs during demo/testing.</div>
"""

if count == 0:
    footer_html += "<div class='debug-item'>No errors logged yet.</div>"
else:
    for item in reversed(log):
        footer_html += f"""
        <div class="debug-item">
          [{item['time']}] <b>{item['title']}</b><br/>
          {item['details']}
        </div>
        """

footer_html += "</details></div>"

st.markdown(footer_html, unsafe_allow_html=True)

# Optional clear button (top of page)
with st.expander("Developer Tools"):
    if st.button("Clear Debug Footer Log"):
        st.session_state.error_log = []
        st.success("Debug log cleared.")
