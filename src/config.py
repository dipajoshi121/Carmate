import os
from pathlib import Path

# Load .env from project root so DATABASE_URL is available (login works without backend)
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass  # optional: pip install python-dotenv

class Config:
    API_BASE = os.environ.get("API_BASE", "http://localhost:4000")
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", "")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").strip().lower() in ("1", "true", "yes", "on")
    PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "sandbox").strip().lower()
    PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
    PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
    PAYPAL_WEBHOOK_ID = os.environ.get("PAYPAL_WEBHOOK_ID", "")

    @property
    def PAYPAL_API_BASE(self):
        if self.PAYPAL_MODE == "live":
            return "https://api-m.paypal.com"
        return "https://api-m.sandbox.paypal.com"

CFG = Config()
