from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from .models import APIKey, UsageLog


class AccountUsageReadAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="usage-reader",
            email="usage-reader@example.test",
            password="safe-test-password",
        )
        self.key, _ = APIKey.issue(user=self.user, name="Reader key")
        self.log = UsageLog.objects.create(
            api_key=self.key,
            endpoint="/api/v1/search/results/",
            method="GET",
            status_code=200,
            latency_ms=42,
        )
        self.client.force_authenticate(user=self.user)

    def test_usage_log_list_returns_the_signed_in_users_recent_rows(self):
        response = self.client.get("/api/v1/account/usage-logs/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["key_name"], "Reader key")
        self.assertEqual(response.data["results"][0]["status_code"], 200)
        self.assertEqual(response.data["results"][0]["latency_ms"], 42)

    def test_analytics_returns_a_seven_day_summary_from_real_usage_rows(self):
        response = self.client.get("/api/v1/account/analytics/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_7d"], 1)
        self.assertEqual(response.data["success_rate"], 100.0)
        self.assertEqual(response.data["average_latency_ms"], 42)
        self.assertEqual(len(response.data["daily"]), 7)
        self.assertEqual(sum(day["count"] for day in response.data["daily"]), 1)

    def test_usage_log_list_never_returns_another_users_rows(self):
        other = User.objects.create_user(
            username="another-reader",
            email="another-reader@example.test",
            password="safe-test-password",
        )
        other_key, _ = APIKey.issue(user=other, name="Another key")
        UsageLog.objects.create(
            api_key=other_key,
            endpoint="/private/other-user/",
            method="GET",
            status_code=200,
            latency_ms=10,
        )

        response = self.client.get("/api/v1/account/usage-logs/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["endpoint"], "/api/v1/search/results/")
