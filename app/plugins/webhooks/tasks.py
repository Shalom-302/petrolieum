# app/plugins/webhooks/tasks.py

import requests
import hmac
import hashlib
from celery import Celery
from . import celeryconfig

# Create a Celery app instance for webhooks
celery_app = Celery("webhooks")
celery_app.config_from_object(celeryconfig)


@celery_app.task
def deliver_webhook(
    webhook_id: int,
    url: str,
    event: str,
    payload: dict,
    secret: str = ""
):
    """
    Actually POST the webhook to 'url' with JSON payload.
    Optionally sign it with 'secret' (e.g. in an HMAC header).
    """
    headers = {"Content-Type": "application/json"}

    # Example: sign the payload if secret is given
    if secret:
        # Convert payload to JSON string
        import json
        body_str = json.dumps(payload, separators=(",", ":"))
        signature = hmac.new(
            secret.encode("utf-8"),
            body_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        headers["X-Webhook-Signature"] = signature

    # You could also include the event name in a custom header
    headers["X-Webhook-Event"] = event

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        r.raise_for_status()
        return {
            "webhook_id": webhook_id,
            "status_code": r.status_code,
            "response_body": r.text[:500]  # store partial for debugging
        }
    except Exception as e:
        # In production, you'd do logging/retries
        return {"webhook_id": webhook_id, "error": str(e)}
