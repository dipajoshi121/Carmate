import json
from decimal import Decimal, InvalidOperation

import requests

from config import CFG


class PaymentError(Exception):
    pass


def _validate_amount(amount) -> Decimal:
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError) as e:
        raise PaymentError("Invalid payment amount.") from e
    if value <= 0:
        raise PaymentError("Payment amount must be greater than zero.")
    return value.quantize(Decimal("0.01"))


def _paypal_token() -> str:
    if not CFG.PAYPAL_CLIENT_ID or not CFG.PAYPAL_CLIENT_SECRET:
        raise PaymentError("PayPal Sandbox credentials are missing in environment variables.")
    token_url = f"{CFG.PAYPAL_API_BASE}/v1/oauth2/token"
    resp = requests.post(
        token_url,
        data={"grant_type": "client_credentials"},
        auth=(CFG.PAYPAL_CLIENT_ID, CFG.PAYPAL_CLIENT_SECRET),
        timeout=20,
    )
    if resp.status_code != 200:
        raise PaymentError(f"Could not authenticate with PayPal ({resp.status_code}).")
    data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
    token = data.get("access_token")
    if not token:
        raise PaymentError("PayPal token missing in auth response.")
    return token


def create_paypal_order(amount, currency: str = "USD", description: str = "Carmate service payment"):
    """Create a PayPal Sandbox order and return dict with order/approval links."""
    value = _validate_amount(amount)
    token = _paypal_token()
    url = f"{CFG.PAYPAL_API_BASE}/v2/checkout/orders"
    body = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "amount": {"currency_code": (currency or "USD").upper(), "value": str(value)},
                "description": description,
            }
        ],
    }
    resp = requests.post(
        url,
        json=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        detail = resp.text
        try:
            detail = resp.json()
        except Exception:
            pass
        raise PaymentError(f"PayPal order creation failed ({resp.status_code}): {detail}")
    data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
    approve_url = None
    for link in data.get("links", []):
        if link.get("rel") == "approve":
            approve_url = link.get("href")
            break
    return {
        "order_id": data.get("id"),
        "status": data.get("status"),
        "approve_url": approve_url,
        "raw": data,
    }


def capture_paypal_order(order_id: str):
    if not order_id or not str(order_id).strip():
        raise PaymentError("Order ID is required.")
    token = _paypal_token()
    oid = str(order_id).strip()
    url = f"{CFG.PAYPAL_API_BASE}/v2/checkout/orders/{oid}/capture"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        detail = resp.text
        try:
            detail = resp.json()
        except Exception:
            pass
        raise PaymentError(f"PayPal capture failed ({resp.status_code}): {detail}")
    data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
    capture_id = None
    for pu in data.get("purchase_units", []):
        payments = pu.get("payments", {})
        captures = payments.get("captures", []) if isinstance(payments, dict) else []
        if captures:
            capture_id = captures[0].get("id")
            break
    return {"status": data.get("status"), "capture_id": capture_id, "raw": data}


def verify_paypal_webhook(headers: dict, event_body: dict) -> bool:
    """Verify PayPal webhook signature using VERIFY-WEBHOOK-SIGNATURE endpoint."""
    if not CFG.PAYPAL_WEBHOOK_ID:
        raise PaymentError("PAYPAL_WEBHOOK_ID is missing.")
    token = _paypal_token()
    verify_url = f"{CFG.PAYPAL_API_BASE}/v1/notifications/verify-webhook-signature"
    payload = {
        "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID") or headers.get("paypal-transmission-id"),
        "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME") or headers.get("paypal-transmission-time"),
        "cert_url": headers.get("PAYPAL-CERT-URL") or headers.get("paypal-cert-url"),
        "auth_algo": headers.get("PAYPAL-AUTH-ALGO") or headers.get("paypal-auth-algo"),
        "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG") or headers.get("paypal-transmission-sig"),
        "webhook_id": CFG.PAYPAL_WEBHOOK_ID,
        "webhook_event": event_body,
    }
    resp = requests.post(
        verify_url,
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    )
    if resp.status_code != 200:
        return False
    data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
    return data.get("verification_status") == "SUCCESS"


def parse_webhook_body(body_text: str) -> dict:
    try:
        return json.loads(body_text or "{}")
    except Exception as e:
        raise PaymentError("Invalid webhook JSON payload.") from e


def create_payment_request_api(*, request_id: str, user_id: str, amount, currency: str = "USD", description: str = "Carmate service payment"):
    """
    API-like function for creating a payment request with validation + transaction storage.
    Returns dict:
      {
        "transaction": <db row>,
        "order_id": "...",
        "approve_url": "...",
        "status": "..."
      }
    """
    if not request_id or not str(request_id).strip():
        raise PaymentError("Request ID is required.")
    if not user_id or not str(user_id).strip():
        raise PaymentError("User ID is required.")
    value = _validate_amount(amount)

    order = create_paypal_order(amount=value, currency=currency, description=description)
    from db import create_payment_transaction
    tx = create_payment_transaction(
        request_id=str(request_id),
        user_id=str(user_id),
        amount=value,
        currency=currency,
        provider="paypal",
        paypal_order_id=order.get("order_id"),
        status=(order.get("status") or "created").lower(),
        raw_response=order.get("raw"),
    )
    if not tx:
        raise PaymentError("Could not store transaction record.")
    return {
        "transaction": tx,
        "order_id": order.get("order_id"),
        "approve_url": order.get("approve_url"),
        "status": order.get("status"),
    }
