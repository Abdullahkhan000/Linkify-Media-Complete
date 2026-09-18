import json
import hashlib
import hmac
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from .middleware import demo_token
from .models import (
    APIKey,
    BillingWebhookEvent,
    SupportConversation,
    SupportMessage,
    SupportTicket,
    UsageLog,
)

User = get_user_model()


class SupportBotTests(TestCase):
    def setUp(self):
        cache.clear()

    def post_json(self, url_name, payload):
        return self.client.post(
            reverse(url_name),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_chat_uses_safe_fallback_without_api_key(self):
        response = self.post_json("support-chat", {"message": "How do I use my API key?"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source"], "fallback")
        self.assertIn("X-API-Key", body["message"])
        self.assertEqual(SupportConversation.objects.count(), 1)
        self.assertEqual(SupportMessage.objects.filter(role="user").count(), 1)
        self.assertEqual(SupportMessage.objects.filter(role="assistant").count(), 1)

    def test_escalation_creates_ticket_with_transcript(self):
        chat_response = self.post_json(
            "support-chat",
            {"message": "I need a human because I have a billing issue."},
        )
        self.assertEqual(chat_response.status_code, 200)
        conversation_id = chat_response.json()["conversation_id"]

        ticket_response = self.post_json(
            "support-ticket-create",
            {
                "conversation_id": conversation_id,
                "name": "Test User",
                "email": "test@example.com",
                "subject": "Billing help",
            },
        )

        self.assertEqual(ticket_response.status_code, 201)
        self.assertEqual(SupportTicket.objects.count(), 1)
        ticket = SupportTicket.objects.get()
        self.assertEqual(str(ticket.conversation_id), conversation_id)
        self.assertIn("billing issue", ticket.message)
        self.assertEqual(ticket.priority, "urgent")

    def test_chat_rejects_another_session_conversation(self):
        first = self.post_json("support-chat", {"message": "Hello support"})
        conversation_id = first.json()["conversation_id"]
        self.client.cookies.clear()

        response = self.post_json(
            "support-chat",
            {"conversation_id": conversation_id, "message": "Can I access this?"},
        )

        self.assertEqual(response.status_code, 403)


class SecureSignupAndAPIKeyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="owner@example.com", email="owner@example.com", password="safe-test-password")
        self.client.force_login(self.user)

    def test_landing_signup_redirects_without_issuing_credentials(self):
        self.client.logout()
        response = self.client.post('/', {'name': 'New Owner', 'email': 'new@example.com'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/accounts/signup/')
        self.assertFalse(User.objects.filter(email='new@example.com').exists())
        self.assertEqual(APIKey.objects.count(), 0)

        signup = self.client.get(response['Location'])
        self.assertContains(signup, 'value="new@example.com"')

    def test_unverified_user_cannot_create_key(self):
        response = self.client.post('/api/keys/', {'name': 'Production'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_key_is_shown_once_and_stored_as_hash(self):
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True, primary=True)
        response = self.client.post(
            '/api/keys/',
            json.dumps({'name': 'Production', 'scopes': ['search', 'usage']}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        raw_key = response.json()['key']
        key = APIKey.objects.get()
        self.assertTrue(raw_key.startswith(APIKey.SECRET_PREFIX))
        self.assertNotEqual(key.key_hash, raw_key)
        self.assertEqual(key.key_hash, APIKey.digest_secret(raw_key))

        listing = self.client.get('/api/keys/').json()[0]
        self.assertNotIn('key', listing)
        self.assertIn('masked_key', listing)

        usage = self.client.get('/api/v1/usage/', HTTP_X_API_KEY=raw_key)
        self.assertEqual(usage.status_code, 200)
        self.assertEqual(UsageLog.objects.count(), 1)

        self.client.delete(f'/api/keys/{key.pk}/')
        denied = self.client.get('/api/v1/usage/', HTTP_X_API_KEY=raw_key)
        self.assertEqual(denied.status_code, 401)


@override_settings(DEMO_API_ENABLED=True, TMDB_API_KEY='')
class DemoAndPageRegressionTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_faq_and_public_health_pages_load(self):
        self.assertEqual(self.client.get('/faq/').status_code, 200)
        self.assertEqual(self.client.get('/api/health/').status_code, 200)
        self.assertEqual(self.client.get('/api/schema/').status_code, 200)
        self.assertEqual(self.client.get('/api/docs/').status_code, 200)

    def test_hardcoded_demo_key_is_rejected_and_signed_token_is_bounded(self):
        rejected = self.client.get('/api/v1/search/?q=Dune', HTTP_X_API_KEY='demo_key')
        self.assertEqual(rejected.status_code, 401)

        malformed = self.client.post(
            '/api/v1/batch/',
            json.dumps({'items': ['not-an-object']}),
            content_type='application/json',
            HTTP_X_DEMO_TOKEN=demo_token(),
        )
        self.assertEqual(malformed.status_code, 400)

    def test_support_form_returns_json_and_creates_ticket(self):
        response = self.client.post(
            '/support/',
            {'name': 'Visitor', 'email': 'visitor@example.com', 'subject': 'API help', 'category': 'api', 'message': 'Please help.'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['ok'])
        self.assertEqual(SupportTicket.objects.count(), 1)

    @override_settings(TMDB_API_KEY='configured-for-mocked-test')
    def test_versioned_discovery_endpoints_return_structured_data(self):
        async def fake_provider(path, params=None, cache_ttl=900):
            item = {'id': 1, 'title': 'Dune', 'release_date': '2021-10-22', 'vote_average': 8.1}
            if path == 'search/person':
                return {'results': [{'id': 2, 'name': 'Actor', 'known_for': [item]}]}
            if path.startswith('movie/1'):
                return {
                    **item,
                    'credits': {'cast': [], 'crew': []},
                    'recommendations': {'results': [item]},
                    'watch/providers': {'results': {'US': {'flatrate': []}}},
                    'external_ids': {'imdb_id': 'tt1160419'},
                }
            return {'page': 1, 'total_pages': 1, 'total_results': 1, 'results': [item]}

        headers = {'HTTP_X_DEMO_TOKEN': demo_token()}
        with patch('api.views.fetch_tmdb_endpoint', new=fake_provider):
            search = self.client.get('/api/v1/search/results/?q=Dune&type=movie', **headers)
            detail = self.client.get('/api/v1/media/movie/1/?country=us', **headers)
            trending = self.client.get('/api/v1/trending/?type=movie', **headers)
            people = self.client.get('/api/v1/people/search/?q=Actor', **headers)
        self.assertEqual([search.status_code, detail.status_code, trending.status_code, people.status_code], [200, 200, 200, 200])
        self.assertEqual(search.json()['results'][0]['title'], 'Dune')
        self.assertIn('watch_providers', detail.json())
        self.assertEqual(trending.json()['results'][0]['title'], 'Dune')
        self.assertEqual(people.json()['results'][0]['name'], 'Actor')


class BillingWebhookSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='billing@example.com', email='billing@example.com')

    def payload(self, event_name='subscription_created', event_id='evt_1', tier='pro'):
        return json.dumps({
            'meta': {'event_name': event_name, 'event_id': event_id, 'custom_data': {'user_id': str(self.user.pk), 'tier': tier}},
            'data': {'id': 'sub_123', 'attributes': {'customer_id': 456}},
        }).encode()

    def test_missing_secret_fails_closed(self):
        response = self.client.post('/billing/webhook/', data=self.payload(), content_type='application/json')
        self.assertEqual(response.status_code, 503)

    @override_settings(LEMONSQUEEZY_WEBHOOK_SECRET='test-webhook-secret')
    def test_signed_webhook_is_idempotent_and_cancellation_downgrades(self):
        body = self.payload()
        signature = hmac.new(b'test-webhook-secret', body, hashlib.sha256).hexdigest()
        first = self.client.post('/billing/webhook/', data=body, content_type='application/json', HTTP_X_SIGNATURE=signature)
        second = self.client.post('/billing/webhook/', data=body, content_type='application/json', HTTP_X_SIGNATURE=signature)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.tier, 'pro')
        self.assertEqual(BillingWebhookEvent.objects.count(), 1)

        cancelled = self.payload('subscription_cancelled', 'evt_2', 'pro')
        cancel_signature = hmac.new(b'test-webhook-secret', cancelled, hashlib.sha256).hexdigest()
        response = self.client.post('/billing/webhook/', data=cancelled, content_type='application/json', HTTP_X_SIGNATURE=cancel_signature)
        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.tier, 'free')
