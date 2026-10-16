from unittest.mock import AsyncMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import APIKey, UsageLog


@override_settings(SECURE_SSL_REDIRECT=False)
class PlaygroundTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username='playground_dev')
        self.key, self.secret = APIKey.issue(user=self.user, name='Playground', scopes=['search','usage','batch'])

    def test_page_requires_login_and_never_renders_secrets(self):
        self.assertEqual(self.client.get('/playground/').status_code,302)
        self.client.force_login(self.user)
        response = self.client.get('/playground/')
        self.assertContains(response,'API Playground')
        self.assertNotContains(response,self.secret)
        self.assertNotContains(response,self.key.key_hash)
        self.assertEqual(response['Cache-Control'],'private, no-store')

    def test_live_endpoint_usage_headers_and_quota_match(self):
        response = self.client.get('/api/v1/usage/',HTTP_X_API_KEY=self.secret)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['today_usage'],1)
        self.assertEqual(response['X-Quota-Cost'],'1')
        self.assertEqual(response['X-Quota-Limit'],'100')
        self.assertEqual(response['X-Quota-Remaining'],'99')
        self.assertEqual(response['Cache-Control'],'private, no-store')
        self.assertEqual(UsageLog.objects.get().status_code,200)

    def test_validation_errors_cost_one_and_invalid_keys_cost_none(self):
        response = self.client.get('/api/v1/search/',HTTP_X_API_KEY=self.secret)
        self.assertEqual(response.status_code,400)
        self.assertEqual(response['X-Quota-Cost'],'1')
        rejected = self.client.get('/api/v1/usage/',HTTP_X_API_KEY='invalid')
        self.assertEqual(rejected.status_code,401)
        self.assertNotIn('X-Quota-Cost',rejected)
        self.assertEqual(UsageLog.objects.count(),1)

    def test_scope_and_daily_limit_cannot_be_bypassed(self):
        _, search_only = APIKey.issue(user=self.user,name='Search only',scopes=['search'])
        self.assertEqual(self.client.get('/api/v1/usage/',HTTP_X_API_KEY=search_only).status_code,403)
        with patch('api.middleware.DAILY_LIMITS',{'free':1}):
            self.assertEqual(self.client.get('/api/v1/usage/',HTTP_X_API_KEY=self.secret).status_code,200)
            self.assertEqual(self.client.get('/api/v1/usage/',HTTP_X_API_KEY=self.secret).status_code,429)
        self.assertEqual(UsageLog.objects.count(),1)

    def test_unlimited_plan_headers(self):
        self.user.profile.tier='business'
        self.user.profile.save()
        response=self.client.get('/api/v1/usage/',HTTP_X_API_KEY=self.secret)
        self.assertEqual(response['X-Quota-Remaining'],'unlimited')
        self.assertEqual(response['X-Quota-Limit'],'unlimited')

    def test_batch_api_key_works_without_browser_csrf_cookie(self):
        self.user.profile.tier='pro'
        self.user.profile.save()
        client=Client(enforce_csrf_checks=True)
        with patch('api.views.fetch_media_links',AsyncMock(return_value={'title':'Inception'})):
            response=client.post('/api/v1/batch/',{'items':[{'q':'Inception'}]},content_type='application/json',HTTP_X_API_KEY=self.secret)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['X-Quota-Cost'],'1')
        self.assertEqual(client.post('/api/v1/batch/',{},content_type='application/json').status_code,401)

    def test_expired_key_rejected(self):
        self.key.expires_at=timezone.now()
        self.key.save()
        self.assertEqual(self.client.get('/api/v1/usage/',HTTP_X_API_KEY=self.secret).status_code,401)
        self.assertFalse(UsageLog.objects.exists())
