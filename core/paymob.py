import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)
PAYMOB_API = "https://accept.paymob.com/api"


class PaymobError(Exception):
    pass


def _post_json(path, payload):
    request = urllib.request.Request(
        f"{PAYMOB_API}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.exception("Paymob API request failed")
        raise PaymobError("Paymob could not be reached. Please try again.") from exc
    if not isinstance(result, dict):
        raise PaymobError("Paymob returned an unexpected response.")
    return result


def create_checkout(payment, user):
    required = (
        settings.PAYMOB_API_KEY,
        settings.PAYMOB_INTEGRATION_ID,
        settings.PAYMOB_IFRAME_ID,
    )
    if not all(required):
        raise PaymobError(
            "Online checkout is not configured yet. Please contact KemetX support."
        )

    auth = _post_json("/auth/tokens", {"api_key": settings.PAYMOB_API_KEY})
    auth_token = auth.get("token")
    if not auth_token:
        raise PaymobError("Paymob authentication did not return a token.")

    order = _post_json(
        "/ecommerce/orders",
        {
            "auth_token": auth_token,
            "delivery_needed": False,
            "amount_cents": payment.amount_cents,
            "currency": "EGP",
            "merchant_order_id": str(payment.merchant_order_id),
            "items": [],
        },
    )
    paymob_order_id = order.get("id")
    if not paymob_order_id:
        raise PaymobError("Paymob did not create an order.")

    billing_data = {
        "apartment": "NA",
        "email": user.email or "customer@kemetx.local",
        "floor": "NA",
        "first_name": user.first_name or user.username,
        "street": "NA",
        "building": "NA",
        "phone_number": getattr(getattr(user, "profile", None), "phone", ""),
        "postal_code": "00000",
        "city": getattr(getattr(user, "profile", None), "city", "") or "Cairo",
        "country": "EG",
        "last_name": user.last_name or user.username,
        "state": "Cairo",
    }
    key_response = _post_json(
        "/acceptance/payment_keys",
        {
            "auth_token": auth_token,
            "amount_cents": payment.amount_cents,
            "expiration": 3600,
            "order_id": paymob_order_id,
            "billing_data": billing_data,
            "currency": "EGP",
            "integration_id": settings.PAYMOB_INTEGRATION_ID,
            "lock_order_when_paid": True,
        },
    )
    payment_key = key_response.get("token")
    if not payment_key:
        raise PaymobError("Paymob did not create a checkout key.")
    return (
        f"https://accept.paymob.com/api/acceptance/iframes/"
        f"{settings.PAYMOB_IFRAME_ID}?payment_token={payment_key}",
        str(paymob_order_id),
    )
