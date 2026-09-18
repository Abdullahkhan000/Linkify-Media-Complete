import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import BillingEvent, BillingSubscription, Profile, WebhookDelivery, WebhookEndpoint
from .tasks import apply_billing_event, deliver_webhook, dispatch_due_webhook_retries


User = get_user_model()


class WebhookHardeningTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="hooks-user", email="hooks@example.com", password="safe-password-123")
        self.endpoint = WebhookEndpoint.objects.create(
            user=self.user,
            name="Test endpoint",
            url="https://example.com/hook",
            secret="endpoint-secret",
            events=["endpoint.test"],
        )

    @patch("api.tasks.requests.post")
    def test_successful_delivery_is_signed_and_completed(self, post):
        post.return_value = Mock(status_code=200, text="accepted")
        delivery = WebhookDelivery.objects.create(
            endpoint=self.endpoint,
            event="endpoint.test",
            payload={"z": 1, "a": 2},
            next_attempt_at=timezone.now(),
        )

        result = deliver_webhook.run(delivery.pk)

        delivery.refresh_from_db()
        self.assertEqual(result["status"], "delivered")
        self.assertTrue(delivery.success)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertIsNotNone(delivery.completed_at)
        raw = json.dumps(delivery.payload, separators=(",", ":"), sort_keys=True).encode()
        expected = hmac.new(self.endpoint.secret.encode(), raw, hashlib.sha256).hexdigest()
        self.assertEqual(post.call_args.kwargs["headers"]["X-Linkify-Signature"], expected)

    @patch("api.tasks.requests.post")
    def test_failed_delivery_schedules_exponential_retry(self, post):
        post.return_value = Mock(status_code=503, text="busy")
        delivery = WebhookDelivery.objects.create(
            endpoint=self.endpoint,
            event="endpoint.test",
            payload={"ok": True},
            next_attempt_at=timezone.now(),
        )

        result = deliver_webhook.run(delivery.pk)

        delivery.refresh_from_db()
        self.assertEqual(result["status"], "retry_scheduled")
        self.assertFalse(delivery.success)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertEqual(delivery.status_code, 503)
        self.assertIsNotNone(delivery.next_attempt_at)
        self.assertIsNone(delivery.completed_at)
        self.assertIn("HTTP 503", delivery.last_error)

    @patch("api.tasks.deliver_webhook.delay")
    def test_due_retry_dispatcher_queues_due_deliveries(self, delay):
        delivery = WebhookDelivery.objects.create(
            endpoint=self.endpoint,
            event="endpoint.test",
            payload={},
            next_attempt_at=timezone.now() - timedelta(seconds=1),
        )
        result = dispatch_due_webhook_retries.run()
        self.assertEqual(result, {"queued": 1})
        delay.assert_called_once_with(delivery.pk)

    @patch("api.tasks.requests.post")
    def test_max_attempts_marks_delivery_exhausted(self, post):
        post.return_value = Mock(status_code=500, text="error")
        self.endpoint.max_attempts = 1
        self.endpoint.save(update_fields=["max_attempts"])
        delivery = WebhookDelivery.objects.create(
            endpoint=self.endpoint,
            event="endpoint.test",
            payload={},
            next_attempt_at=timezone.now(),
        )
        deliver_webhook.run(delivery.pk)
        delivery.refresh_from_db()
        self.assertFalse(delivery.success)
        self.assertIsNotNone(delivery.completed_at)
        self.assertIsNone(delivery.next_attempt_at)


@override_settings(LEMONSQUEEZY_WEBHOOK_SECRET="webhook-secret", LEMONSQUEEZY_VARIANT_PRO="101")
class BillingHardeningTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="billing-user", email="billing@example.com", password="safe-password-123")
        self.client = Client()

    def _payload(self, event_name="subscription_created"):
        return {
            "meta": {
                "event_name": event_name,
                "custom_data": {"user_id": self.user.id, "tier": "pro", "variant_id": "101"},
            },
            "data": {
                "id": "sub-123",
                "type": "subscriptions",
                "attributes": {
                    "status": "active",
                    "variant_id": 101,
                    "customer_id": 77,
                    "store_id": 88,
                    "renews_at": "2026-09-01T00:00:00Z",
                    "urls": {"customer_portal": "https://app.lemonsqueezy.com/my-orders/portal"},
                },
            },
        }

    @patch("api.billing_views.process_billing_event.delay")
    def test_signed_billing_webhook_is_idempotent(self, delay):
        payload = self._payload()
        raw = json.dumps(payload, separators=(",", ":")).encode()
        signature = hmac.new(b"webhook-secret", raw, hashlib.sha256).hexdigest()
        url = reverse("lemonsqueezy-webhook")

        first = self.client.post(url, data=raw, content_type="application/json", HTTP_X_SIGNATURE=signature)
        second = self.client.post(url, data=raw, content_type="application/json", HTTP_X_SIGNATURE=signature)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(BillingEvent.objects.count(), 1)
        delay.assert_called_once()

    def test_invalid_billing_signature_is_rejected(self):
        raw = json.dumps(self._payload(), separators=(",", ":")).encode()
        response = self.client.post(
            reverse("lemonsqueezy-webhook"),
            data=raw,
            content_type="application/json",
            HTTP_X_SIGNATURE="bad-signature",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(BillingEvent.objects.count(), 0)

    def test_billing_event_updates_profile_and_subscription(self):
        event = BillingEvent.objects.create(
            event_id="subscription_created:sub-123",
            event_name="subscription_created",
            payload=self._payload(),
        )
        self.assertTrue(apply_billing_event(event))
        profile = Profile.objects.get(user=self.user)
        subscription = BillingSubscription.objects.get(user=self.user)
        self.assertEqual(profile.tier, "pro")
        self.assertEqual(profile.subscription_id, "sub-123")
        self.assertEqual(subscription.status, "active")
        self.assertEqual(subscription.customer_portal_url, "https://app.lemonsqueezy.com/my-orders/portal")

    def test_expired_event_downgrades_profile_to_free(self):
        payload = self._payload("subscription_expired")
        payload["data"]["attributes"]["status"] = "expired"
        event = BillingEvent.objects.create(
            event_id="subscription_expired:sub-123",
            event_name="subscription_expired",
            payload=payload,
        )
        apply_billing_event(event)
        self.assertEqual(Profile.objects.get(user=self.user).tier, "free")


class MFARouteTests(TestCase):
    def test_mfa_index_route_is_available_for_authenticated_user(self):
        user = User.objects.create_user(username="mfa-user", email="mfa@example.com", password="safe-password-123")
        self.client.force_login(user)
        response = self.client.get(reverse("mfa_index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Two-factor authentication")


class HardeningPageAndQueueTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="page-user", email="page@example.com", password="safe-password-123")
        self.endpoint = WebhookEndpoint.objects.create(
            user=self.user,
            name="Page endpoint",
            url="https://example.com/hook",
            secret="endpoint-secret",
            events=["endpoint.test"],
        )
        self.client.force_login(self.user)

    def test_billing_and_webhook_pages_render(self):
        billing = self.client.get(reverse("billing"))
        webhooks = self.client.get(reverse("webhooks-page"))
        self.assertEqual(billing.status_code, 200)
        self.assertContains(billing, "Pricing Plans")
        self.assertEqual(webhooks.status_code, 200)
        self.assertContains(webhooks, "Recent deliveries")

    @patch("api.tasks.deliver_webhook.delay")
    def test_webhook_test_is_persisted_and_queued(self, delay):
        response = self.client.post(reverse("webhook-test-api", kwargs={"pk": self.endpoint.pk}), data={}, content_type="application/json")
        self.assertEqual(response.status_code, 202)
        delivery = WebhookDelivery.objects.get(endpoint=self.endpoint)
        self.assertEqual(response.json()["delivery_id"], delivery.pk)
        delay.assert_called_once_with(delivery.pk)

    @patch("api.tasks.deliver_webhook.delay")
    def test_manual_retry_requeues_failed_delivery(self, delay):
        delivery = WebhookDelivery.objects.create(
            endpoint=self.endpoint,
            event="endpoint.test",
            payload={},
            completed_at=timezone.now(),
            last_error="previous failure",
        )
        response = self.client.post(reverse("webhook-retry-api", kwargs={"pk": delivery.pk}), data={}, content_type="application/json")
        delivery.refresh_from_db()
        self.assertEqual(response.status_code, 202)
        self.assertIsNone(delivery.completed_at)
        self.assertIsNotNone(delivery.next_attempt_at)
        delay.assert_called_once_with(delivery.pk)
