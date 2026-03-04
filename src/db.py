import hashlib
import json
import os
import secrets
from datetime import datetime, timezone, timedelta
from uuid import UUID

class DatabaseError(Exception):
    pass

def _hash_password(password: str) -> str:
    salt = os.environ.get("PASSWORD_SALT", "carmate-default-salt")
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

def get_connection():
    import psycopg2
    from psycopg2 import OperationalError
    url = os.environ.get("DATABASE_URL")
    if not url or not url.strip():
        return None
    url = url.strip()
    if "sslmode" not in url and "neon.tech" in url:
        url += "&sslmode=require" if "?" in url else "?sslmode=require"
    try:
        return psycopg2.connect(url)
    except OperationalError as e:
        raise DatabaseError(f"Connection failed: {e}") from e
    except Exception as e:
        raise DatabaseError(f"Database error: {e}") from e

def _conn():
    return get_connection()

def _cur(conn, dict_cursor=True):
    from psycopg2.extras import RealDictCursor
    return conn.cursor(cursor_factory=RealDictCursor if dict_cursor else None)

def _json(val):
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    return json.loads(val) if isinstance(val, str) else val

def create_user(email: str, password: str, full_name: str = None, phone: str = None):
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                """INSERT INTO users (email, password_hash, full_name, phone)
                   VALUES (%s, %s, %s, %s)
                   RETURNING id, email, full_name, phone, is_active, created_at""",
                (email.strip().lower(), _hash_password(password), full_name or "", phone or ""),
            )
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    except Exception as e:
        conn.rollback()
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()

def get_user_by_email(email: str):
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                "SELECT id, email, password_hash, full_name, phone, is_active, created_at, updated_at FROM users WHERE email = %s LIMIT 1",
                (email.strip().lower(),),
            )
            row = cur.fetchone()
        return dict(row) if row else None
    except DatabaseError:
        raise
    except Exception as e:
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()

def get_user_by_id(user_id) -> dict | None:
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                "SELECT id, email, full_name, phone, is_active, created_at, updated_at FROM users WHERE id = %s LIMIT 1",
                (str(user_id),),
            )
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def verify_password(email: str, password: str) -> dict | None:
    u = get_user_by_email(email)
    if not u or not u.get("password_hash"):
        return None
    if _hash_password(password) != u["password_hash"]:
        return None
    return {k: v for k, v in u.items() if k != "password_hash"}

def update_user(user_id, full_name: str = None, email: str = None, phone: str = None, password: str = None):
    conn = _conn()
    if not conn:
        return None
    try:
        updates = ["updated_at = now()"]
        args = []
        if full_name is not None:
            updates.append("full_name = %s")
            args.append(full_name)
        if email is not None:
            updates.append("email = %s")
            args.append(email.strip().lower())
        if phone is not None:
            updates.append("phone = %s")
            args.append(phone)
        if password:
            updates.append("password_hash = %s")
            args.append(_hash_password(password))
        args.append(str(user_id))
        with _cur(conn) as cur:
            cur.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = %s RETURNING id, email, full_name, phone, is_active",
                args,
            )
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()

def list_users():
    conn = _conn()
    if not conn:
        return []
    try:
        with _cur(conn) as cur:
            cur.execute("SELECT id, email, full_name, phone, is_active, created_at FROM users ORDER BY created_at DESC")
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def set_user_active(user_id, is_active: bool):
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute("UPDATE users SET is_active = %s, updated_at = now() WHERE id = %s RETURNING id, is_active", (is_active, str(user_id)))
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()

def create_password_reset_token(email: str, expires_hours: int = 24) -> str | None:
    conn = _conn()
    if not conn:
        return None
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    try:
        with _cur(conn, dict_cursor=False) as cur:
            cur.execute(
                "INSERT INTO password_reset_tokens (email, token, expires_at) VALUES (%s, %s, %s)",
                (email.strip().lower(), token, expires_at),
            )
        conn.commit()
        return token
    except DatabaseError:
        raise
    except Exception as e:
        conn.rollback()
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()

def user_exists_by_email(email: str) -> bool:
    return get_user_by_email(email) is not None

def get_valid_reset_token(token: str) -> dict | None:
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                "SELECT email, expires_at FROM password_reset_tokens WHERE token = %s AND used_at IS NULL AND expires_at > now() LIMIT 1",
                (token,),
            )
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def mark_reset_token_used(token: str):
    conn = _conn()
    if not conn:
        return False
    try:
        with _cur(conn, dict_cursor=False) as cur:
            cur.execute("UPDATE password_reset_tokens SET used_at = now() WHERE token = %s", (token,))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()

def create_service_request(user_id, vehicle: dict, service_type: str, description: str = ""):
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                """INSERT INTO service_requests (user_id, vehicle, service_type, description, status)
                   VALUES (%s, %s, %s, %s, 'Pending')
                   RETURNING id, user_id, vehicle, service_type, description, status, estimate, created_at""",
                (str(user_id), json.dumps(vehicle or {}), service_type or "Service", description or ""),
            )
            row = cur.fetchone()
        conn.commit()
        if row:
            r = dict(row)
            r["vehicle"] = _json(r.get("vehicle"))
            r["estimate"] = _json(r.get("estimate"))
            return r
        return None
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()

def get_my_requests(user_id):
    conn = _conn()
    if not conn:
        return []
    try:
        with _cur(conn) as cur:
            cur.execute(
                """SELECT id, user_id, vehicle, service_type, description, status, estimate, created_at, updated_at
                   FROM service_requests WHERE user_id = %s ORDER BY created_at DESC""",
                (str(user_id),),
            )
            rows = cur.fetchall()
        out = []
        for r in rows:
            o = dict(r)
            o["vehicle"] = _json(o.get("vehicle"))
            o["estimate"] = _json(o.get("estimate"))
            out.append(o)
        return out
    except DatabaseError:
        raise
    except Exception as e:
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()

def get_request_by_id(request_id, user_id=None):
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            if user_id:
                cur.execute(
                    """SELECT id, user_id, vehicle, service_type, description, status, estimate, created_at, updated_at
                       FROM service_requests WHERE id = %s AND user_id = %s LIMIT 1""",
                    (str(request_id), str(user_id)),
                )
            else:
                cur.execute(
                    """SELECT id, user_id, vehicle, service_type, description, status, estimate, created_at, updated_at
                       FROM service_requests WHERE id = %s LIMIT 1""",
                    (str(request_id),),
                )
            row = cur.fetchone()
        if not row:
            return None
        o = dict(row)
        o["vehicle"] = _json(o.get("vehicle"))
        o["estimate"] = _json(o.get("estimate"))
        return o
    finally:
        conn.close()

def update_request_estimate(request_id, estimate: dict):
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                """UPDATE service_requests SET estimate = %s, updated_at = now(), status = 'Quoted'
                   WHERE id = %s RETURNING id, estimate, status""",
                (json.dumps(estimate), str(request_id)),
            )
            row = cur.fetchone()
        conn.commit()
        if row:
            o = dict(row)
            o["estimate"] = _json(o.get("estimate"))
            return o
        return None
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()

def update_estimate_status(request_id, status: str):
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                """UPDATE service_requests SET estimate = jsonb_set(COALESCE(estimate, '{}'::jsonb), '{status}', to_jsonb(%s::text)), updated_at = now()
                   WHERE id = %s RETURNING id, estimate""",
                (status, str(request_id)),
            )
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()

def get_request_photos(request_id: str):
    """Return list of {id, request_id, file_path, uploaded_at} for the given request."""
    conn = _conn()
    if not conn:
        return []
    try:
        with _cur(conn) as cur:
            cur.execute(
                "SELECT id, request_id, file_path, uploaded_at FROM service_request_photos WHERE request_id = %s ORDER BY uploaded_at ASC",
                (str(request_id),),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def add_request_photo(request_id: str, file_path: str):
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                "INSERT INTO service_request_photos (request_id, file_path) VALUES (%s, %s) RETURNING id, request_id, file_path, uploaded_at",
                (str(request_id), file_path),
            )
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()
