from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import APIKey, Team, TeamMembership, WebhookEndpoint


User = get_user_model()


class PlatformFeatureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="platform@example.com", email="platform@example.com", password="Strong-pass-123")
        self.user.profile.tier = "pro"
        self.user.profile.save(update_fields=["tier"])
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.client.login(username="platform@example.com", password="Strong-pass-123")

    def test_public_status_and_schema(self):
        status_response = self.client.get(reverse("status-api"))
        schema_response = self.client.get(reverse("openapi-schema"))
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "operational")
        self.assertEqual(schema_response.status_code, 200)
        self.assertEqual(schema_response.json()["openapi"], "3.0.3")

    def test_onboarding_and_key_controls(self):
        response = self.client.post(reverse("onboarding-api"), {"company_name": "Acme", "job_title": "Engineer", "completed": True}, format="json")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.profile.onboarding_completed)

        key = APIKey.objects.create(user=self.user, name="Test key")
        rotate = self.client.post(reverse("api-key-rotate-api", kwargs={"pk": key.pk}))
        self.assertEqual(rotate.status_code, 200)
        key.refresh_from_db()
        self.assertEqual(str(key.key), rotate.json()["key"])
        revoke = self.client.post(reverse("api-key-revoke-api", kwargs={"pk": key.pk}))
        self.assertEqual(revoke.status_code, 200)
        key.refresh_from_db()
        self.assertFalse(key.is_active)

    def test_webhook_creation_and_team_creation(self):
        webhook = self.client.post(reverse("webhooks-api"), {"name": "Primary", "url": "https://example.com/hook", "events": ["media.completed"]}, format="json")
        self.assertEqual(webhook.status_code, 201)
        self.assertTrue(WebhookEndpoint.objects.filter(user=self.user).exists())

        page = self.client.post(reverse("teams"), {"name": "Acme Engineering"})
        self.assertEqual(page.status_code, 302)
        team = Team.objects.get(owner=self.user)
        self.assertTrue(TeamMembership.objects.filter(team=team, user=self.user, role="owner").exists())
