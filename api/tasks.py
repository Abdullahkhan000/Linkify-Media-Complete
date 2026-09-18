import hashlib
import hmac
import json
from datetime import timedelta

import requests
from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import BillingEvent, BillingSubscription, Profile, WebhookDelivery, WebhookEndpoint


User = get_user_model()


WEBHOOK_TIMEOUT = 10
MAX_WEBHOOK_RETRY_DELAY = 3600


def _retry_delay(attempt_count):
    return min(60 * (2 ** max(attempt_count - 1, 0)), MAX_WEBHOOK_RETRY_DELAY)


def _parse_provider_datetime(value):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def _json_bytes(payload):
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def enqueue_webhook_delivery(endpoint, event, payload):
    """Persist a delivery before enqueueing it so every attempt is auditable."""
    delivery = WebhookDelivery.objects.create(
        endpoint=endpoint,
        event=event,
        payload=payload,
        next_attempt_at=timezone.now(),
    )
    deliver_webhook.delay(delivery.pk)
    return delivery


def dispatch_user_webhook_event(user, event, payload):
    """Queue only endpoints subscribed to an event; delivery failures never fail the API job."""
    queued = []
    endpoints = WebhookEndpoint.objects.filter(user=user, is_active=True)
    for endpoint in endpoints:
        if event not in (endpoint.events or []):
            continue
        try:
            queued.append(enqueue_webhook_delivery(endpoint, event, payload).pk)
        except Exception:
            # The primary media request must remain successful if Redis is unavailable.
            continue
    return queued


@shared_task(bind=True, max_retries=0)
def deliver_webhook(self, delivery_id):
    try:
        delivery = WebhookDelivery.objects.select_related("endpoint").get(pk=delivery_id)
    except WebhookDelivery.DoesNotExist:
        return {"status": "missing"}

    endpoint = delivery.endpoint
    if delivery.success or delivery.completed_at or not endpoint.is_active:
        return {"status": "skipped"}

    now = timezone.now()
    if delivery.attempt_count >= endpoint.max_attempts:
        delivery.completed_at = delivery.completed_at or now
        delivery.last_error = delivery.last_error or "Maximum delivery attempts reached."
        delivery.save(update_fields=["completed_at", "last_error"])
        return {"status": "exhausted"}

    delivery.attempt_count += 1
    delivery.last_attempt_at = now
    delivery.save(update_fields=["attempt_count", "last_attempt_at"])

    raw_body = _json_bytes(delivery.payload)
    signature = hmac.new(endpoint.secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "LinkifyMedia-Webhooks/1.0",
        "X-Linkify-Event": delivery.event,
        "X-Linkify-Signature": signature,
        "X-Linkify-Delivery": str(delivery.pk),
    }

    success = False
    status_code = 0
    response_body = ""
    error_message = ""
    try:
        response = requests.post(
            endpoint.url,
            data=raw_body,
            headers=headers,
            timeout=WEBHOOK_TIMEOUT,
        )
        status_code = response.status_code
        response_body = response.text[:2000]
        success = 200 <= response.status_code < 300
        if not success:
            error_message = f"Endpoint returned HTTP {response.status_code}."
    except requests.RequestException as exc:
        error_message = str(exc)[:2000]

    delivery.status_code = status_code
    delivery.success = success
    delivery.response_body = response_body
    delivery.last_error = "" if success else error_message
    delivery.last_attempt_at = now
    delivery.next_attempt_at = None
    delivery.completed_at = now if success else None

    endpoint.last_delivery_at = now
    if success:
        endpoint.failure_count = 0
    else:
        endpoint.failure_count += 1
        if endpoint.retry_enabled and delivery.attempt_count < endpoint.max_attempts:
            delivery.next_attempt_at = now + timedelta(seconds=_retry_delay(delivery.attempt_count))
        else:
            delivery.completed_at = now
    delivery.save(update_fields=[
        "status_code",
        "success",
        "response_body",
        "last_error",
        "last_attempt_at",
        "next_attempt_at",
        "completed_at",
    ])
    endpoint.save(update_fields=["last_delivery_at", "failure_count"])

    return {
        "status": "delivered" if success else "retry_scheduled" if delivery.next_attempt_at else "failed",
        "attempt": delivery.attempt_count,
        "status_code": status_code,
    }


@shared_task
def dispatch_due_webhook_retries():
    """Enqueue deliveries whose backoff window has elapsed."""
    now = timezone.now()
    due_ids = list(
        WebhookDelivery.objects.filter(
            success=False,
            completed_at__isnull=True,
            next_attempt_at__isnull=False,
            next_attempt_at__lte=now,
            endpoint__is_active=True,
        ).values_list("pk", flat=True)[:100]
    )
    for delivery_id in due_ids:
        deliver_webhook.delay(delivery_id)
    return {"queued": len(due_ids)}


def _tier_for_variant(variant_id, fallback="free"):
    variant_id = str(variant_id or "")
    mapping = {}
    pro_variant = str(getattr(settings, "LEMONSQUEEZY_VARIANT_PRO", "") or "")
    business_variant = str(getattr(settings, "LEMONSQUEEZY_VARIANT_BIZ", "") or "")
    if pro_variant:
        mapping[pro_variant] = "pro"
    if business_variant:
        mapping[business_variant] = "business"
    return mapping.get(variant_id, fallback)


def _subscription_status_tier(status, tier):
    if status in {"expired", "unpaid"}:
        return "free"
    return tier


@transaction.atomic
def apply_billing_event(event):
    payload = event.payload or {}
    meta = payload.get("meta") or {}
    data = payload.get("data") or {}
    attributes = data.get("attributes") or {}
    custom_data = meta.get("custom_data") or {}
    event_name = event.event_name

    user = None
    user_id = custom_data.get("user_id")
    if user_id:
        user = User.objects.filter(pk=user_id).first()
    if user is None:
        email = custom_data.get("email") or attributes.get("user_email")
        if email:
            user = User.objects.filter(email__iexact=email).first()
    if user is None:
        # The event is valid but cannot be associated with a local account yet.
        event.processing_error = "No matching local user for billing event."
        return False

    provider_subscription_id = str(data.get("id") or "")
    if not provider_subscription_id:
        event.processing_error = "Billing event did not contain a subscription id."
        return False

    status = attributes.get("status") or {
        "subscription_created": "active",
        "subscription_updated": "active",
        "subscription_resumed": "active",
        "subscription_unpaused": "active",
        "subscription_cancelled": "cancelled",
        "subscription_expired": "expired",
        "subscription_paused": "paused",
        "subscription_payment_failed": "past_due",
        "subscription_payment_success": "active",
        "subscription_payment_recovered": "active",
    }.get(event_name, "active")
    variant_id = str(attributes.get("variant_id") or custom_data.get("variant_id") or "")
    requested_tier = str(custom_data.get("tier") or "free").lower()
    if requested_tier not in {"free", "pro", "business"}:
        requested_tier = "free"
    profile_tier = _tier_for_variant(variant_id, requested_tier)
    effective_tier = _subscription_status_tier(status, profile_tier)

    subscription, _ = BillingSubscription.objects.update_or_create(
        provider_subscription_id=provider_subscription_id,
        defaults={
            "user": user,
            "provider_customer_id": str(attributes.get("customer_id") or ""),
            "store_id": str(attributes.get("store_id") or ""),
            "variant_id": variant_id,
            "tier": profile_tier,
            "status": status,
            "renews_at": _parse_provider_datetime(attributes.get("renews_at")),
            "ends_at": _parse_provider_datetime(attributes.get("ends_at")),
            "customer_portal_url": (attributes.get("urls") or {}).get("customer_portal", ""),
            "update_payment_method_url": (attributes.get("urls") or {}).get("update_payment_method", ""),
            "raw_data": data,
        },
    )

    profile, _ = Profile.objects.get_or_create(user=user)
    profile.tier = effective_tier
    profile.lemonsqueezy_customer_id = str(attributes.get("customer_id") or profile.lemonsqueezy_customer_id or "")
    profile.subscription_id = provider_subscription_id
    profile.subscription_status = status
    profile.subscription_variant_id = variant_id
    profile.subscription_renews_at = subscription.renews_at
    profile.subscription_ends_at = subscription.ends_at
    profile.customer_portal_url = subscription.customer_portal_url
    profile.save(update_fields=[
        "tier",
        "lemonsqueezy_customer_id",
        "subscription_id",
        "subscription_status",
        "subscription_variant_id",
        "subscription_renews_at",
        "subscription_ends_at",
        "customer_portal_url",
    ])
    return True


@shared_task(bind=True, max_retries=4)
def process_billing_event(self, event_id):
    try:
        event = BillingEvent.objects.get(pk=event_id)
        if event.processed:
            return {"status": "already_processed"}
        associated = apply_billing_event(event)
        event.processed = True
        event.processed_at = timezone.now()
        if not associated:
            event.processing_error = event.processing_error or "Event acknowledged without local account update."
        event.save(update_fields=["processed", "processed_at", "processing_error"])
        return {"status": "processed", "associated": associated}
    except Exception as exc:
        try:
            event = BillingEvent.objects.get(pk=event_id)
            event.processing_error = str(exc)[:4000]
            event.save(update_fields=["processing_error"])
        except BillingEvent.DoesNotExist:
            pass
        if self.request.retries >= self.max_retries:
            raise
        raise self.retry(exc=exc, countdown=min(60 * (2 ** self.request.retries), 1800))


@shared_task
def refresh_billing_subscriptions():
    """Refresh local subscription records from Lemon Squeezy for recovery/drift protection."""
    api_key = getattr(settings, "LEMONSQUEEZY_API_KEY", "")
    if not api_key:
        return {"refreshed": 0, "skipped": True}
    refreshed = 0
    headers = {
        "Accept": "application/vnd.api+json",
        "Authorization": f"Bearer {api_key}",
    }
    for subscription in BillingSubscription.objects.exclude(status="expired").iterator():
        try:
            response = requests.get(
                f"https://api.lemonsqueezy.com/v1/subscriptions/{subscription.provider_subscription_id}",
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            body = response.json().get("data") or {}
            attrs = body.get("attributes") or {}
            event = BillingEvent.objects.create(
                event_id=f"refresh:{subscription.provider_subscription_id}:{timezone.now().timestamp()}",
                event_name="subscription_updated",
                payload={"meta": {"custom_data": {"user_id": subscription.user_id}}, "data": body},
            )
            apply_billing_event(event)
            event.processed = True
            event.processed_at = timezone.now()
            event.save(update_fields=["processed", "processed_at"])
            refreshed += 1
        except requests.RequestException:
            continue
    return {"refreshed": refreshed, "skipped": False}
