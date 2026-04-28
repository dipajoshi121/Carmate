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

def create_user(email: str, password: str, full_name: str = None, phone: str = None, role: str = "user"):
    conn = _conn()
    if not conn:
        return None
    r = (role or "user").strip().lower()
    if r not in ("user", "business", "admin"):
        r = "user"
    try:
        with _cur(conn) as cur:
            cur.execute(
                """INSERT INTO users (email, password_hash, full_name, phone, role)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING id, email, full_name, phone, is_active, role, created_at""",
                (email.strip().lower(), _hash_password(password), full_name or "", phone or "", r),
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
                "SELECT id, email, password_hash, full_name, phone, is_active, role, created_at, updated_at FROM users WHERE email = %s LIMIT 1",
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
                "SELECT id, email, full_name, phone, is_active, role, created_at, updated_at FROM users WHERE id = %s LIMIT 1",
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
    out = {k: v for k, v in u.items() if k != "password_hash"}
    if not out.get("role"):
        out["role"] = "user"
    return out

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
            cur.execute(
                "SELECT id, email, full_name, phone, is_active, role, created_at FROM users ORDER BY created_at DESC"
            )
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


def update_password_by_email(email: str, new_password: str) -> bool:
    conn = _conn()
    if not conn:
        return False
    try:
        with _cur(conn, dict_cursor=False) as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s, updated_at = now() WHERE email = %s",
                (_hash_password(new_password), email.strip().lower()),
            )
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()

def create_service_request(user_id, vehicle: dict, service_type: str, description: str = "", preferred_date=None, preferred_time=None, business_creator_id=None):
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                """INSERT INTO service_requests (user_id, vehicle, service_type, description, status, preferred_date, preferred_time, business_creator_id)
                   VALUES (%s, %s, %s, %s, 'Pending', %s, %s, %s)
                   RETURNING id, user_id, vehicle, service_type, description, status, estimate, created_at, preferred_date, preferred_time, business_creator_id""",
                (
                    str(user_id),
                    json.dumps(vehicle or {}),
                    service_type or "Service",
                    description or "",
                    preferred_date,
                    preferred_time,
                    str(business_creator_id) if business_creator_id else None,
                ),
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
                """SELECT id, user_id, vehicle, service_type, description, status, estimate,
                          created_at, updated_at, preferred_date, preferred_time, business_creator_id
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
                    """SELECT id, user_id, vehicle, service_type, description, status, estimate,
                              created_at, updated_at, preferred_date, preferred_time, business_creator_id
                       FROM service_requests WHERE id = %s AND user_id = %s LIMIT 1""",
                    (str(request_id), str(user_id)),
                )
            else:
                cur.execute(
                    """SELECT id, user_id, vehicle, service_type, description, status, estimate,
                              created_at, updated_at, preferred_date, preferred_time, business_creator_id
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

def list_all_service_requests():
    conn = _conn()
    if not conn:
        return []
    try:
        with _cur(conn) as cur:
            cur.execute(
                """SELECT id, user_id, vehicle, service_type, description, status, estimate,
                          created_at, updated_at, preferred_date, preferred_time, business_creator_id
                   FROM service_requests ORDER BY created_at DESC"""
            )
            rows = cur.fetchall()
        out = []
        for r in rows:
            o = dict(r)
            o["vehicle"] = _json(o.get("vehicle"))
            o["estimate"] = _json(o.get("estimate"))
            out.append(o)
        return out
    except Exception as e:
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()

def update_service_request_fields(request_id, status=None, description=None, service_type=None, vehicle=None):
    conn = _conn()
    if not conn:
        return None
    try:
        parts = ["updated_at = now()"]
        args = []
        if status is not None:
            parts.append("status = %s")
            args.append(status)
        if description is not None:
            parts.append("description = %s")
            args.append(description)
        if service_type is not None:
            parts.append("service_type = %s")
            args.append(service_type)
        if vehicle is not None:
            parts.append("vehicle = %s")
            args.append(json.dumps(vehicle))
        args.append(str(request_id))
        with _cur(conn) as cur:
            cur.execute(
                f"""UPDATE service_requests SET {", ".join(parts)}
                    WHERE id = %s
                    RETURNING id, user_id, vehicle, service_type, description, status, estimate, created_at, business_creator_id""",
                args,
            )
            row = cur.fetchone()
        conn.commit()
        if not row:
            return None
        o = dict(row)
        o["vehicle"] = _json(o.get("vehicle"))
        o["estimate"] = _json(o.get("estimate"))
        return o
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()

def set_user_role(user_id, role: str):
    r = (role or "user").strip().lower()
    if r not in ("user", "business", "admin"):
        return None
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                "UPDATE users SET role = %s, updated_at = now() WHERE id = %s RETURNING id, email, role",
                (r, str(user_id)),
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

def delete_service_request(request_id: str, user_id: str | None = None) -> bool:
    """Delete a service request owned by the given user. Returns True if deleted."""
    conn = _conn()
    if not conn:
        return False
    try:
        with _cur(conn, dict_cursor=False) as cur:
            if user_id:
                cur.execute("DELETE FROM service_requests WHERE id = %s AND user_id = %s", (str(request_id), str(user_id)))
            else:
                cur.execute("DELETE FROM service_requests WHERE id = %s", (str(request_id),))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()

def delete_request_photo(photo_id: str, request_id: str | None = None) -> bool:
    """Delete a single photo row. Returns True if deleted."""
    conn = _conn()
    if not conn:
        return False
    try:
        with _cur(conn, dict_cursor=False) as cur:
            if request_id:
                cur.execute(
                    "DELETE FROM service_request_photos WHERE id = %s AND request_id = %s",
                    (str(photo_id), str(request_id)),
                )
            else:
                cur.execute("DELETE FROM service_request_photos WHERE id = %s", (str(photo_id),))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()

def create_payment_transaction(request_id: str, user_id: str, amount, currency: str = "USD", provider: str = "paypal", paypal_order_id: str | None = None, status: str = "created", raw_response=None):
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                """INSERT INTO payment_transactions (request_id, user_id, provider, currency, amount, status, paypal_order_id, raw_response)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id, request_id, user_id, provider, currency, amount, status, paypal_order_id, paypal_capture_id, created_at""",
                (
                    str(request_id),
                    str(user_id),
                    provider or "paypal",
                    (currency or "USD").upper(),
                    amount,
                    status or "created",
                    paypal_order_id,
                    json.dumps(raw_response) if raw_response is not None else None,
                ),
            )
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()

def update_payment_transaction_by_order(paypal_order_id: str, status: str, paypal_capture_id: str | None = None, failure_reason: str | None = None, raw_response=None):
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                """UPDATE payment_transactions
                   SET status = %s,
                       paypal_capture_id = COALESCE(%s, paypal_capture_id),
                       failure_reason = %s,
                       raw_response = COALESCE(%s, raw_response),
                       updated_at = now()
                   WHERE paypal_order_id = %s
                   RETURNING id, request_id, user_id, provider, currency, amount, status, paypal_order_id, paypal_capture_id, updated_at""",
                (
                    status,
                    paypal_capture_id,
                    failure_reason,
                    json.dumps(raw_response) if raw_response is not None else None,
                    paypal_order_id,
                ),
            )
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()

def get_latest_payment_for_request(request_id: str):
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                """SELECT id, request_id, user_id, provider, currency, amount, status, paypal_order_id, paypal_capture_id, failure_reason, created_at, updated_at
                   FROM payment_transactions
                   WHERE request_id = %s
                   ORDER BY created_at DESC
                   LIMIT 1""",
                (str(request_id),),
            )
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def log_payment_webhook_event(provider: str, event_id: str | None, event_type: str | None, verified: bool, payload: dict):
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                """INSERT INTO payment_webhook_events (provider, event_id, event_type, verified, payload)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING id, provider, event_id, event_type, verified, received_at""",
                (
                    provider or "paypal",
                    event_id,
                    event_type,
                    bool(verified),
                    json.dumps(payload or {}),
                ),
            )
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()


def cancel_service_request_by_owner(request_id, owner_user_id) -> dict | None:
    """Set status to Cancelled if the customer owns the request and it is not yet in progress."""
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                """UPDATE service_requests SET status = 'Cancelled', updated_at = now()
                   WHERE id = %s AND user_id = %s AND status IN ('Pending', 'Quoted')
                   RETURNING id, user_id, vehicle, service_type, description, status, estimate, created_at, business_creator_id""",
                (str(request_id), str(owner_user_id)),
            )
            row = cur.fetchone()
        conn.commit()
        if not row:
            return None
        o = dict(row)
        o["vehicle"] = _json(o.get("vehicle"))
        o["estimate"] = _json(o.get("estimate"))
        return o
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()


def get_review_for_request(request_id: str) -> dict | None:
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                """SELECT id, request_id, reviewer_user_id, rating, comment, provider_response,
                          provider_responded_at, created_at, updated_at
                   FROM request_reviews WHERE request_id = %s LIMIT 1""",
                (str(request_id),),
            )
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def upsert_request_review(request_id: str, reviewer_user_id, rating: int, comment: str | None) -> dict | None:
    conn = _conn()
    if not conn:
        return None
    r = int(rating)
    if r < 1 or r > 5:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                """SELECT id, reviewer_user_id FROM request_reviews WHERE request_id = %s LIMIT 1""",
                (str(request_id),),
            )
            existing = cur.fetchone()
            if existing:
                if str(existing.get("reviewer_user_id")) != str(reviewer_user_id):
                    return None
                cur.execute(
                    """UPDATE request_reviews SET rating = %s, comment = %s, updated_at = now()
                       WHERE request_id = %s AND reviewer_user_id = %s
                       RETURNING id, request_id, reviewer_user_id, rating, comment, provider_response,
                                 provider_responded_at, created_at, updated_at""",
                    (r, (comment or "").strip() or None, str(request_id), str(reviewer_user_id)),
                )
            else:
                cur.execute(
                    """INSERT INTO request_reviews (request_id, reviewer_user_id, rating, comment)
                       VALUES (%s, %s, %s, %s)
                       RETURNING id, request_id, reviewer_user_id, rating, comment, provider_response,
                                 provider_responded_at, created_at, updated_at""",
                    (str(request_id), str(reviewer_user_id), r, (comment or "").strip() or None),
                )
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()


def set_provider_review_response(request_id: str, business_user_id: str, response: str) -> dict | None:
    conn = _conn()
    if not conn:
        return None
    text = (response or "").strip()
    if not text:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                """UPDATE request_reviews rr SET
                       provider_response = %s,
                       provider_responded_at = now(),
                       updated_at = now()
                   FROM service_requests sr
                   WHERE rr.request_id = sr.id
                     AND rr.request_id = %s
                     AND sr.business_creator_id IS NOT NULL
                     AND sr.business_creator_id::text = %s
                   RETURNING rr.id, rr.request_id, rr.reviewer_user_id, rr.rating, rr.comment,
                             rr.provider_response, rr.provider_responded_at, rr.created_at, rr.updated_at""",
                (text, str(request_id), str(business_user_id)),
            )
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()


def create_review_report(review_id: str, reporter_user_id: str, reason: str) -> dict | None:
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                """SELECT reviewer_user_id FROM request_reviews WHERE id = %s LIMIT 1""",
                (str(review_id),),
            )
            rev = cur.fetchone()
            if not rev or str(rev.get("reviewer_user_id")) == str(reporter_user_id):
                return None
            cur.execute(
                """INSERT INTO review_reports (review_id, reporter_user_id, reason, status)
                   VALUES (%s, %s, %s, 'open')
                   RETURNING id, review_id, reporter_user_id, reason, status, created_at""",
                (str(review_id), str(reporter_user_id), (reason or "").strip() or None),
            )
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()


def list_open_review_reports():
    conn = _conn()
    if not conn:
        return []
    try:
        with _cur(conn) as cur:
            cur.execute(
                """SELECT rp.id, rp.review_id, rp.reporter_user_id, rp.reason, rp.status, rp.created_at,
                          rev.request_id, rev.rating, rev.comment, rev.reviewer_user_id
                   FROM review_reports rp
                   JOIN request_reviews rev ON rev.id = rp.review_id
                   WHERE rp.status = 'open'
                   ORDER BY rp.created_at DESC"""
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def resolve_review_report(report_id: str, status: str, admin_notes: str | None = None) -> dict | None:
    resolved_status = (status or "").strip().lower()
    if resolved_status not in ("dismissed", "resolved"):
        return None
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                """UPDATE review_reports SET status = %s, resolved_at = now(), admin_notes = %s
                   WHERE id = %s AND status = 'open'
                   RETURNING id, review_id, status, resolved_at, admin_notes""",
                (resolved_status, (admin_notes or "").strip() or None, str(report_id)),
            )
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()


def business_rating_summary(business_user_id: str) -> dict | None:
    conn = _conn()
    if not conn:
        return None
    try:
        with _cur(conn) as cur:
            cur.execute(
                """SELECT ROUND(AVG(rr.rating)::numeric, 2) AS avg_rating, COUNT(rr.id)::int AS review_count
                   FROM service_requests sr
                   INNER JOIN request_reviews rr ON rr.request_id = sr.id
                   WHERE sr.business_creator_id::text = %s""",
                (str(business_user_id),),
            )
            row = cur.fetchone()
        if not row:
            return None
        o = dict(row)
        if o.get("review_count") == 0:
            return {"avg_rating": None, "review_count": 0}
        return o
    finally:
        conn.close()


def list_businesses_with_ratings():
    conn = _conn()
    if not conn:
        return []
    try:
        with _cur(conn) as cur:
            cur.execute(
                """SELECT u.id, u.email, u.full_name,
                          ROUND(AVG(rr.rating)::numeric, 2) AS avg_rating,
                          COUNT(rr.id)::int AS review_count
                   FROM users u
                   LEFT JOIN service_requests sr ON sr.business_creator_id = u.id
                   LEFT JOIN request_reviews rr ON rr.request_id = sr.id
                   WHERE u.role = 'business'
                   GROUP BY u.id, u.email, u.full_name
                   ORDER BY avg_rating DESC NULLS LAST, u.full_name NULLS LAST"""
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _ensure_request_chat_table(conn):
    with _cur(conn, dict_cursor=False) as cur:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS request_chat_messages (
                   id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                   request_id UUID NOT NULL REFERENCES service_requests(id) ON DELETE CASCADE,
                   sender_user_id TEXT,
                   sender_role TEXT NOT NULL,
                   sender_name TEXT,
                   message TEXT NOT NULL,
                   created_at TIMESTAMPTZ NOT NULL DEFAULT now()
               )"""
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_request_chat_messages_req_created ON request_chat_messages(request_id, created_at)"
        )


def list_request_chat_messages(request_id: str, limit: int = 200):
    conn = _conn()
    if not conn:
        return []
    lim = max(1, min(int(limit or 200), 500))
    try:
        _ensure_request_chat_table(conn)
        with _cur(conn) as cur:
            cur.execute(
                """SELECT id, request_id, sender_user_id, sender_role, sender_name, message, created_at
                   FROM request_chat_messages
                   WHERE request_id = %s
                   ORDER BY created_at ASC
                   LIMIT %s""",
                (str(request_id), lim),
            )
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()


def add_request_chat_message(request_id: str, sender_user_id, sender_role: str, sender_name: str | None, message: str):
    conn = _conn()
    if not conn:
        return None
    text = (message or "").strip()
    if not text:
        return None
    role = (sender_role or "user").strip().lower()
    if role not in ("user", "business", "admin"):
        role = "user"
    try:
        _ensure_request_chat_table(conn)
        with _cur(conn) as cur:
            cur.execute(
                """INSERT INTO request_chat_messages (request_id, sender_user_id, sender_role, sender_name, message)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING id, request_id, sender_user_id, sender_role, sender_name, message, created_at""",
                (
                    str(request_id),
                    str(sender_user_id) if sender_user_id else None,
                    role,
                    (sender_name or "").strip() or None,
                    text,
                ),
            )
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()
