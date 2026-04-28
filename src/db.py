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
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    try:
        # 6-digit numeric OTP-style reset code.
        for _ in range(10):
            token = f"{secrets.randbelow(1_000_000):06d}"
            try:
                with _cur(conn, dict_cursor=False) as cur:
                    cur.execute(
                        "INSERT INTO password_reset_tokens (email, token, expires_at) VALUES (%s, %s, %s)",
                        (email.strip().lower(), token, expires_at),
                    )
                conn.commit()
                return token
            except Exception as ie:
                conn.rollback()
                # Retry only on token collision; fail fast for other DB issues.
                if "duplicate key value" in str(ie).lower():
                    continue
                raise
        raise DatabaseError("Could not allocate unique reset code.")
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


def _ensure_request_estimates_table(conn):
    with _cur(conn, dict_cursor=False) as cur:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS request_estimates (
                   id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                   request_id UUID NOT NULL REFERENCES service_requests(id) ON DELETE CASCADE,
                   business_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                   business_name TEXT,
                   currency TEXT NOT NULL DEFAULT 'USD',
                   labor NUMERIC(12,2) NOT NULL DEFAULT 0,
                   parts NUMERIC(12,2) NOT NULL DEFAULT 0,
                   tax NUMERIC(12,2) NOT NULL DEFAULT 0,
                   fees NUMERIC(12,2) NOT NULL DEFAULT 0,
                   total NUMERIC(12,2) NOT NULL DEFAULT 0,
                   notes TEXT,
                   valid_until DATE,
                   status TEXT NOT NULL DEFAULT 'submitted',
                   created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                   updated_at TIMESTAMPTZ DEFAULT now(),
                   UNIQUE (request_id, business_user_id)
               )"""
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_request_estimates_request_id ON request_estimates(request_id)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_request_estimates_business_user_id ON request_estimates(business_user_id)"
        )


def upsert_request_estimate(
    request_id: str,
    business_user_id: str,
    business_name: str | None,
    estimate: dict,
):
    conn = _conn()
    if not conn:
        return None
    try:
        _ensure_request_estimates_table(conn)
        with _cur(conn) as cur:
            cur.execute(
                """INSERT INTO request_estimates (
                       request_id, business_user_id, business_name, currency, labor, parts, tax, fees, total, notes, valid_until, status
                   )
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (request_id, business_user_id)
                   DO UPDATE SET
                       business_name = EXCLUDED.business_name,
                       currency = EXCLUDED.currency,
                       labor = EXCLUDED.labor,
                       parts = EXCLUDED.parts,
                       tax = EXCLUDED.tax,
                       fees = EXCLUDED.fees,
                       total = EXCLUDED.total,
                       notes = EXCLUDED.notes,
                       valid_until = EXCLUDED.valid_until,
                       status = EXCLUDED.status,
                       updated_at = now()
                   RETURNING id, request_id, business_user_id, business_name, currency, labor, parts, tax, fees, total, notes, valid_until, status, created_at, updated_at""",
                (
                    str(request_id),
                    str(business_user_id),
                    (business_name or "").strip() or None,
                    (estimate.get("currency") or "USD").upper(),
                    estimate.get("labor") or 0,
                    estimate.get("parts") or 0,
                    estimate.get("tax") or 0,
                    estimate.get("fees") or 0,
                    estimate.get("total") or 0,
                    (estimate.get("notes") or "").strip() or None,
                    estimate.get("valid_until"),
                    (estimate.get("status") or "submitted").strip().lower(),
                ),
            )
            row = cur.fetchone()
            cur.execute(
                "UPDATE service_requests SET status = 'Quoted', updated_at = now() WHERE id = %s AND status IN ('Pending', 'Quoted')",
                (str(request_id),),
            )
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()


def list_request_estimates(request_id: str):
    conn = _conn()
    if not conn:
        return []
    try:
        _ensure_request_estimates_table(conn)
        with _cur(conn) as cur:
            cur.execute(
                """SELECT id, request_id, business_user_id, business_name, currency, labor, parts, tax, fees, total,
                          notes, valid_until, status, created_at, updated_at
                   FROM request_estimates
                   WHERE request_id = %s
                   ORDER BY created_at ASC""",
                (str(request_id),),
            )
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()


def set_request_estimate_status(estimate_id: str, status: str):
    conn = _conn()
    if not conn:
        return None
    new_status = (status or "").strip().lower()
    if new_status not in ("submitted", "accepted", "rejected"):
        return None
    try:
        _ensure_request_estimates_table(conn)
        with _cur(conn) as cur:
            cur.execute(
                """SELECT request_id FROM request_estimates WHERE id = %s LIMIT 1""",
                (str(estimate_id),),
            )
            row = cur.fetchone()
            if not row:
                return None
            req_id = str(row.get("request_id"))
            if new_status == "accepted":
                cur.execute(
                    """UPDATE request_estimates
                       SET status = CASE WHEN id = %s THEN 'accepted' ELSE status END,
                           updated_at = now()
                       WHERE request_id = %s""",
                    (str(estimate_id), req_id),
                )
                cur.execute(
                    """UPDATE request_estimates
                       SET status = 'submitted', updated_at = now()
                       WHERE request_id = %s AND id <> %s AND status = 'accepted'""",
                    (req_id, str(estimate_id)),
                )
            else:
                cur.execute(
                    "UPDATE request_estimates SET status = %s, updated_at = now() WHERE id = %s",
                    (new_status, str(estimate_id)),
                )
            cur.execute(
                """SELECT id, request_id, business_user_id, business_name, currency, labor, parts, tax, fees, total,
                          notes, valid_until, status, created_at, updated_at
                   FROM request_estimates WHERE id = %s LIMIT 1""",
                (str(estimate_id),),
            )
            out = cur.fetchone()
        conn.commit()
        return dict(out) if out else None
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
                   counterparty_business_user_id TEXT,
                   receiver_user_id TEXT,
                   is_read BOOLEAN NOT NULL DEFAULT FALSE,
                   read_at TIMESTAMPTZ,
                   sender_name TEXT,
                   message TEXT NOT NULL,
                   created_at TIMESTAMPTZ NOT NULL DEFAULT now()
               )"""
        )
        cur.execute(
            "ALTER TABLE request_chat_messages ADD COLUMN IF NOT EXISTS counterparty_business_user_id TEXT"
        )
        cur.execute(
            "ALTER TABLE request_chat_messages ADD COLUMN IF NOT EXISTS receiver_user_id TEXT"
        )
        cur.execute(
            "ALTER TABLE request_chat_messages ADD COLUMN IF NOT EXISTS is_read BOOLEAN NOT NULL DEFAULT FALSE"
        )
        cur.execute(
            "ALTER TABLE request_chat_messages ADD COLUMN IF NOT EXISTS read_at TIMESTAMPTZ"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_request_chat_messages_req_created ON request_chat_messages(request_id, created_at)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_request_chat_messages_req_biz_created ON request_chat_messages(request_id, counterparty_business_user_id, created_at)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_request_chat_messages_receiver_unread ON request_chat_messages(receiver_user_id, is_read)"
        )


def _get_request_chat_participants(conn, request_id: str):
    with _cur(conn) as cur:
        cur.execute(
            """SELECT user_id, business_creator_id
               FROM service_requests
               WHERE id = %s
               LIMIT 1""",
            (str(request_id),),
        )
        row = cur.fetchone()
    if not row:
        return None, None
    return str(row.get("user_id") or ""), str(row.get("business_creator_id") or "")


def _list_request_business_participants(conn, request_id: str):
    out = set()
    try:
        with _cur(conn) as cur:
            cur.execute(
                """SELECT business_user_id
                   FROM request_estimates
                   WHERE request_id = %s""",
                (str(request_id),),
            )
            for r in cur.fetchall():
                bid = str(r.get("business_user_id") or "")
                if bid:
                    out.add(bid)
    except Exception:
        # request_estimates table may not exist yet in older environments.
        pass
    return out


def _can_access_request_chat(
    owner_user_id: str,
    business_participants: set[str],
    viewer_user_id,
    viewer_role: str | None,
) -> bool:
    vuid = str(viewer_user_id or "")
    vrole = (viewer_role or "").strip().lower()
    # Private chat: only request owner customer or participating business account.
    if vrole == "user" and owner_user_id and vuid == owner_user_id:
        return True
    if vrole == "business" and vuid in business_participants:
        return True
    return False


def list_request_chat_messages(
    request_id: str,
    limit: int = 200,
    viewer_user_id=None,
    viewer_role: str | None = None,
    counterparty_business_user_id: str | None = None,
):
    conn = _conn()
    if not conn:
        return []
    lim = max(1, min(int(limit or 200), 500))
    try:
        _ensure_request_chat_table(conn)
        owner_uid, _ = _get_request_chat_participants(conn, request_id)
        biz_participants = _list_request_business_participants(conn, request_id)
        if not _can_access_request_chat(owner_uid, biz_participants, viewer_user_id, viewer_role):
            return []
        vuid = str(viewer_user_id or "")
        vrole = (viewer_role or "").strip().lower()
        if vrole == "business":
            thread_biz_uid = vuid
        elif vrole == "user":
            thread_biz_uid = str(counterparty_business_user_id or "").strip()
            if thread_biz_uid not in biz_participants:
                return []
        else:
            return []
        with _cur(conn) as cur:
            cur.execute(
                """SELECT id, request_id, sender_user_id, sender_role, counterparty_business_user_id, receiver_user_id,
                          is_read, read_at, sender_name, message, created_at
                   FROM request_chat_messages
                   WHERE request_id = %s AND counterparty_business_user_id = %s
                   ORDER BY created_at ASC
                   LIMIT %s""",
                (str(request_id), thread_biz_uid, lim),
            )
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()


def add_request_chat_message(
    request_id: str,
    sender_user_id,
    sender_role: str,
    sender_name: str | None,
    message: str,
    counterparty_business_user_id: str | None = None,
):
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
        owner_uid, _ = _get_request_chat_participants(conn, request_id)
        biz_participants = _list_request_business_participants(conn, request_id)
        if not _can_access_request_chat(owner_uid, biz_participants, sender_user_id, role):
            return None
        sender_uid = str(sender_user_id or "")
        if role == "business":
            thread_biz_uid = sender_uid
        elif role == "user":
            thread_biz_uid = str(counterparty_business_user_id or "").strip()
            if thread_biz_uid not in biz_participants:
                return None
        else:
            return None
        receiver_uid = owner_uid if role == "business" else thread_biz_uid
        if not receiver_uid:
            return None
        with _cur(conn) as cur:
            cur.execute(
                """INSERT INTO request_chat_messages (
                       request_id, sender_user_id, sender_role, counterparty_business_user_id,
                       receiver_user_id, is_read, read_at, sender_name, message
                   )
                   VALUES (%s, %s, %s, %s, %s, FALSE, NULL, %s, %s)
                   RETURNING id, request_id, sender_user_id, sender_role, counterparty_business_user_id,
                             receiver_user_id, is_read, read_at, sender_name, message, created_at""",
                (
                    str(request_id),
                    sender_uid if sender_uid else None,
                    role,
                    thread_biz_uid,
                    receiver_uid,
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


def list_user_chat_conversations(viewer_user_id, viewer_role: str | None, limit: int = 200):
    conn = _conn()
    if not conn:
        return []
    vuid = str(viewer_user_id or "")
    vrole = (viewer_role or "").strip().lower()
    lim = max(1, min(int(limit or 200), 500))
    if not vuid or vrole not in ("user", "business"):
        return []
    try:
        _ensure_request_chat_table(conn)
        with _cur(conn) as cur:
            if vrole == "user":
                cur.execute(
                    """WITH allowed_threads AS (
                           SELECT re.request_id, re.business_user_id::text AS business_user_id, COALESCE(re.business_name, 'Business') AS business_name
                           FROM request_estimates re
                           JOIN service_requests sr ON sr.id = re.request_id
                           WHERE sr.user_id = %s
                           GROUP BY re.request_id, re.business_user_id::text, COALESCE(re.business_name, 'Business')
                       ),
                       latest_message AS (
                           SELECT DISTINCT ON (m.request_id, m.counterparty_business_user_id)
                                  m.request_id, m.counterparty_business_user_id, m.message, m.created_at,
                                  m.sender_user_id, m.sender_role
                           FROM request_chat_messages m
                           ORDER BY m.request_id, m.counterparty_business_user_id, m.created_at DESC
                       ),
                       unread_by_thread AS (
                           SELECT m.request_id, m.counterparty_business_user_id, COUNT(*)::int AS unread_count
                           FROM request_chat_messages m
                           WHERE m.receiver_user_id = %s AND COALESCE(m.is_read, FALSE) = FALSE
                           GROUP BY m.request_id, m.counterparty_business_user_id
                       )
                       SELECT at.request_id, at.business_user_id AS counterparty_business_user_id, at.business_name,
                              lm.message AS latest_message, lm.created_at AS latest_message_at,
                              COALESCE(ubt.unread_count, 0) AS unread_count
                       FROM allowed_threads at
                       LEFT JOIN latest_message lm
                         ON lm.request_id = at.request_id AND lm.counterparty_business_user_id = at.business_user_id
                       LEFT JOIN unread_by_thread ubt
                         ON ubt.request_id = at.request_id AND ubt.counterparty_business_user_id = at.business_user_id
                       ORDER BY COALESCE(lm.created_at, now() - interval '100 years') DESC
                       LIMIT %s""",
                    (vuid, vuid, lim),
                )
            else:
                cur.execute(
                    """WITH allowed_threads AS (
                           SELECT re.request_id, re.business_user_id::text AS business_user_id
                           FROM request_estimates re
                           WHERE re.business_user_id = %s
                           GROUP BY re.request_id, re.business_user_id::text
                       ),
                       latest_message AS (
                           SELECT DISTINCT ON (m.request_id, m.counterparty_business_user_id)
                                  m.request_id, m.counterparty_business_user_id, m.message, m.created_at,
                                  m.sender_user_id, m.sender_role
                           FROM request_chat_messages m
                           ORDER BY m.request_id, m.counterparty_business_user_id, m.created_at DESC
                       ),
                       unread_by_thread AS (
                           SELECT m.request_id, m.counterparty_business_user_id, COUNT(*)::int AS unread_count
                           FROM request_chat_messages m
                           WHERE m.receiver_user_id = %s AND COALESCE(m.is_read, FALSE) = FALSE
                           GROUP BY m.request_id, m.counterparty_business_user_id
                       )
                       SELECT at.request_id, at.business_user_id AS counterparty_business_user_id,
                              COALESCE(u.full_name, u.email, 'Customer') AS customer_name,
                              lm.message AS latest_message, lm.created_at AS latest_message_at,
                              COALESCE(ubt.unread_count, 0) AS unread_count
                       FROM allowed_threads at
                       JOIN service_requests sr ON sr.id = at.request_id
                       LEFT JOIN users u ON u.id = sr.user_id
                       LEFT JOIN latest_message lm
                         ON lm.request_id = at.request_id AND lm.counterparty_business_user_id = at.business_user_id
                       LEFT JOIN unread_by_thread ubt
                         ON ubt.request_id = at.request_id AND ubt.counterparty_business_user_id = at.business_user_id
                       ORDER BY COALESCE(lm.created_at, now() - interval '100 years') DESC
                       LIMIT %s""",
                    (vuid, vuid, lim),
                )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()


def mark_request_chat_thread_read(
    request_id: str,
    counterparty_business_user_id: str,
    viewer_user_id,
    viewer_role: str | None,
):
    conn = _conn()
    if not conn:
        return 0
    vuid = str(viewer_user_id or "")
    vrole = (viewer_role or "").strip().lower()
    thread_biz_uid = str(counterparty_business_user_id or "").strip()
    if not vuid or vrole not in ("user", "business") or not thread_biz_uid:
        return 0
    try:
        _ensure_request_chat_table(conn)
        owner_uid, _ = _get_request_chat_participants(conn, request_id)
        biz_participants = _list_request_business_participants(conn, request_id)
        if not _can_access_request_chat(owner_uid, biz_participants, viewer_user_id, viewer_role):
            return 0
        if vrole == "user" and thread_biz_uid not in biz_participants:
            return 0
        if vrole == "business" and vuid != thread_biz_uid:
            return 0
        with _cur(conn) as cur:
            cur.execute(
                """UPDATE request_chat_messages
                   SET is_read = TRUE, read_at = now()
                   WHERE request_id = %s
                     AND counterparty_business_user_id = %s
                     AND receiver_user_id = %s
                     AND COALESCE(is_read, FALSE) = FALSE""",
                (str(request_id), thread_biz_uid, vuid),
            )
            updated = cur.rowcount or 0
        conn.commit()
        return int(updated)
    except Exception:
        conn.rollback()
        return 0
    finally:
        conn.close()
