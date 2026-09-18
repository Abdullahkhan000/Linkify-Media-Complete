import requests
from django.conf import settings


LEMONSQUEEZY_API_BASE = "https://api.lemonsqueezy.com/v1"


class BillingConfigurationError(Exception):
    pass


def _headers():
    api_key = getattr(settings, "LEMONSQUEEZY_API_KEY", "")
    if not api_key:
        raise BillingConfigurationError("Lemon Squeezy API credentials are not configured.")
    return {
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
        "Authorization": f"Bearer {api_key}",
    }


def lemonsqueezy_request(method, path, *, payload=None, timeout=20):
    response = requests.request(
        method,
        f"{LEMONSQUEEZY_API_BASE}{path}",
        headers=_headers(),
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def create_checkout(*, user, tier):
    variant_id = {
        "pro": getattr(settings, "LEMONSQUEEZY_VARIANT_PRO", ""),
        "business": getattr(settings, "LEMONSQUEEZY_VARIANT_BIZ", ""),
    }.get(tier, "")
    store_id = getattr(settings, "LEMONSQUEEZY_STORE_ID", "")
    if not variant_id or not store_id:
        raise BillingConfigurationError("Lemon Squeezy store and variant IDs are not configured.")

    payload = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "checkout_data": {
                    "email": user.email,
                    "custom": {
                        "user_id": str(user.id),
                        "email": user.email,
                        "tier": tier,
                        "variant_id": str(variant_id),
                    },
                },
            },
            "relationships": {
                "store": {"data": {"type": "stores", "id": str(store_id)}},
                "variant": {"data": {"type": "variants", "id": str(variant_id)}},
            },
        }
    }
    body = lemonsqueezy_request("POST", "/checkouts", payload=payload)
    return body["data"]["attributes"]["url"]


def cancel_subscription(subscription_id):
    body = lemonsqueezy_request("DELETE", f"/subscriptions/{subscription_id}")
    return body.get("data") or {}


def resume_subscription(subscription_id):
    payload = {
        "data": {
            "type": "subscriptions",
            "id": str(subscription_id),
            "attributes": {"cancelled": False},
        }
    }
    body = lemonsqueezy_request("PATCH", f"/subscriptions/{subscription_id}", payload=payload)
    return body.get("data") or {}


def update_subscription_variant(subscription_id, variant_id, *, disable_prorations=True):
    payload = {
        "data": {
            "type": "subscriptions",
            "id": str(subscription_id),
            "attributes": {
                "variant_id": int(variant_id),
                "disable_prorations": disable_prorations,
            },
        }
    }
    body = lemonsqueezy_request("PATCH", f"/subscriptions/{subscription_id}", payload=payload)
    return body.get("data") or {}


def refresh_subscription(subscription_id):
    body = lemonsqueezy_request("GET", f"/subscriptions/{subscription_id}")
    return body.get("data") or {}
