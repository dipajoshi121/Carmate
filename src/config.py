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

CFG = Config()
