import os
import secrets
from datetime import datetime, timezone, timedelta

def get_connection():
    import psycopg2
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    return psycopg2.connect(url)

def create_password_reset_token(email: str, expires_hours: int = 24) -> str | None:
    conn = get_connection()
    if not conn:
        return None
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO password_reset_tokens (email, token, expires_at)
                VALUES (%s, %s, %s)
                """,
                (email.strip().lower(), token, expires_at),
            )
        conn.commit()
        return token
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()

def user_exists_by_email(email: str) -> bool:
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE email = %s LIMIT 1", (email.strip().lower(),))
            return cur.fetchone() is not None
    finally:
        conn.close()
