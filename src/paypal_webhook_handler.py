"""
Reusable PayPal webhook handler logic.

Hook this function into your backend endpoint that receives PayPal webhooks:
    POST /api/payments/paypal/webhook
"""

from payments import verify_paypal_webhook, parse_webhook_body
from db import log_payment_webhook_event, update_payment_transaction_by_order


def handle_paypal_webhook(headers: dict, body_text: str) -> dict:
    """
    Validate and process PayPal webhook payload.
    Returns:
      {"ok": bool, "verified": bool, "event_type": str, "event_id": str}
    """
    event = parse_webhook_body(body_text)
    verified = verify_paypal_webhook(headers, event)

    event_id = event.get("id")
    event_type = event.get("event_type")
    log_payment_webhook_event(
        provider="paypal",
        event_id=event_id,
        event_type=event_type,
        verified=verified,
        payload=event,
    )

    if not verified:
        return {"ok": False, "verified": False, "event_type": event_type, "event_id": event_id}

    resource = event.get("resource") or {}
    order_id = (
        resource.get("supplementary_data", {})
        .get("related_ids", {})
        .get("order_id")
        or resource.get("id")
    )

    if event_type == "PAYMENT.CAPTURE.COMPLETED" and order_id:
        update_payment_transaction_by_order(
            paypal_order_id=order_id,
            status="completed",
            paypal_capture_id=resource.get("id"),
            raw_response=event,
        )
    elif event_type in ("PAYMENT.CAPTURE.DENIED", "PAYMENT.CAPTURE.REVERSED") and order_id:
        update_payment_transaction_by_order(
            paypal_order_id=order_id,
            status="failed",
            failure_reason=event_type,
            raw_response=event,
        )

    return {"ok": True, "verified": True, "event_type": event_type, "event_id": event_id}
