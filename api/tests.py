import json
import hashlib
import hmac
import os
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from allauth.socialaccount.models import SocialApp
from django.test import TestCase
from django.test.utils import override_settings
from django.template.loader import get_template
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

    @override_settings(ACCOUNT_EMAIL_VERIFICATION='mandatory')
    def test_unverified_user_cannot_create_key_when_verification_is_enabled(self):
        response = self.client.post('/api/keys/', {'name': 'Production'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    @override_settings(ACCOUNT_EMAIL_VERIFICATION='none')
    def test_launch_mode_allows_key_creation_without_verification(self):
        response = self.client.post(
            '/api/keys/',
            json.dumps({'name': 'Launch', 'scopes': ['search', 'usage']}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['key'].startswith(APIKey.SECRET_PREFIX))

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


class HeadlessAccountFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.session_url = "/_allauth/browser/v1/auth/session"

    def post_json(self, path, payload):
        return self.client.post(path, json.dumps(payload), content_type="application/json")

    def test_signup_requires_terms_and_password_confirmation(self):
        payload = {
            "username": "next_builder",
            "email": "next@example.com",
            "password": "secure-next-password-42",
            "password_confirm": "secure-next-password-42",
        }
        rejected = self.post_json("/_allauth/browser/v1/auth/signup", payload)
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.json()["errors"][0]["param"], "terms")

        payload["terms"] = True
        created = self.post_json("/_allauth/browser/v1/auth/signup", payload)
        self.assertEqual(created.status_code, 200)
        self.assertTrue(created.json()["meta"]["is_authenticated"])
        self.assertTrue(User.objects.filter(username="next_builder").exists())

    def test_login_change_password_and_logout_headless_flow(self):
        user = User.objects.create_user(
            username="account_owner",
            email="owner-next@example.com",
            password="original-password-42",
        )
        EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=False)
        login = self.post_json("/_allauth/browser/v1/auth/login", {
            "email": user.email,
            "password": "original-password-42",
        })
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json()["meta"]["is_authenticated"])

        changed = self.post_json("/_allauth/browser/v1/account/password/change", {
            "current_password": "original-password-42",
            "new_password": "replacement-password-77",
        })
        self.assertEqual(changed.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password("replacement-password-77"))

        logged_out = self.client.delete(self.session_url)
        self.assertEqual(logged_out.status_code, 401)
        self.assertFalse(logged_out.json()["meta"]["is_authenticated"])

    @override_settings(FRONTEND_URL="http://localhost:3000")
    def test_password_reset_email_targets_next_frontend(self):
        user = User.objects.create_user(
            username="reset_owner",
            email="reset-next@example.com",
            password="original-password-42",
        )
        EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
        response = self.post_json("/_allauth/browser/v1/auth/password/request", {"email": user.email})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("http://localhost:3000/reset-password/", mail.outbox[0].body)

    def test_profile_update_and_password_confirmed_deletion_api(self):
        user = User.objects.create_user(
            username="delete_owner",
            email="delete-next@example.com",
            password="delete-password-42",
        )
        self.client.force_login(user)
        updated = self.client.patch(
            "/api/v1/account/profile/",
            json.dumps({"username": "renamed_owner", "first_name": "Link", "last_name": "Builder"}),
            content_type="application/json",
        )
        self.assertEqual(updated.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.username, "renamed_owner")

        rejected = self.client.delete(
            "/api/v1/account/delete/",
            json.dumps({"confirmation": "renamed_owner", "password": "wrong-password"}),
            content_type="application/json",
        )
        self.assertEqual(rejected.status_code, 400)
        deleted = self.client.delete(
            "/api/v1/account/delete/",
            json.dumps({"confirmation": "renamed_owner", "password": "delete-password-42"}),
            content_type="application/json",
        )
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(User.objects.filter(pk=user.pk).exists())

    def test_all_declared_account_templates_compile(self):
        templates = [
            "account/account_inactive.html",
            "account/auth_base.html",
            "account/email_change.html",
            "account/email_confirm.html",
            "account/login.html",
            "account/logout.html",
            "account/password_change.html",
            "account/password_reset.html",
            "account/password_reset_done.html",
            "account/password_reset_from_key.html",
            "account/password_reset_from_key_done.html",
            "account/password_set.html",
            "account/reauthenticate.html",
            "account/signup.html",
            "account/verification_sent.html",
            "account/verified_email_required.html",
            "socialaccount/authentication_error.html",
            "socialaccount/connections.html",
            "socialaccount/login.html",
            "socialaccount/login_cancelled.html",
            "socialaccount/login_redirect.html",
            "socialaccount/signup.html",
        ]
        for template_name in templates:
            with self.subTest(template=template_name):
                self.assertIsNotNone(get_template(template_name))

    def test_headless_google_redirect_is_exposed_only_when_configured(self):
        empty_config = self.client.get("/_allauth/browser/v1/config").json()
        self.assertEqual(empty_config["data"]["socialaccount"]["providers"], [])

        site, _ = Site.objects.update_or_create(
            id=1,
            defaults={"domain": "testserver", "name": "Test"},
        )
        app = SocialApp.objects.create(
            provider="google",
            name="Google",
            client_id="headless-client",
            secret="headless-secret",
        )
        app.sites.add(site)

        configured = self.client.get("/_allauth/browser/v1/config").json()
        self.assertEqual(
            configured["data"]["socialaccount"]["providers"][0]["id"],
            "google",
        )
        redirect_response = self.client.post(
            "/_allauth/browser/v1/auth/provider/redirect",
            {
                "provider": "google",
                "process": "login",
                "callback_url": "http://localhost:3000/dashboard",
            },
        )
        self.assertEqual(redirect_response.status_code, 302)
        self.assertTrue(redirect_response["Location"].startswith("https://accounts.google.com/"))


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


@override_settings(ACCOUNT_EMAIL_VERIFICATION='none')
class CompleteAccountFlowTests(TestCase):
    password = 'Strong-launch-password-941!'

    def signup(self, username='launch_user', email='launch@example.com'):
        return self.client.post('/accounts/signup/', {
            'username': username,
            'email': email,
            'password1': self.password,
            'password2': self.password,
            'terms': 'on',
        })

    def test_signup_creates_account_and_logs_user_in_without_verification(self):
        response = self.signup()
        self.assertRedirects(response, '/dashboard/', fetch_redirect_response=False)
        user = User.objects.get(username='launch_user')
        self.assertEqual(user.email, 'launch@example.com')
        self.assertEqual(str(self.client.session['_auth_user_id']), str(user.pk))
        self.assertTrue(EmailAddress.objects.filter(user=user, email=user.email, primary=True).exists())

    def test_signup_requires_server_side_terms_acceptance(self):
        response = self.client.post('/accounts/signup/', {
            'username': 'no_terms',
            'email': 'no-terms@example.com',
            'password1': self.password,
            'password2': self.password,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Accept the Terms and Privacy Policy')
        self.assertFalse(User.objects.filter(username='no_terms').exists())

    def test_login_accepts_username_and_email(self):
        self.signup()
        self.client.post('/accounts/logout/')

        by_username = self.client.post('/accounts/login/', {
            'login': 'launch_user', 'password': self.password,
        })
        self.assertRedirects(by_username, '/dashboard/', fetch_redirect_response=False)
        self.client.post('/accounts/logout/')

        by_email = self.client.post('/accounts/login/', {
            'login': 'launch@example.com', 'password': self.password,
        })
        self.assertRedirects(by_email, '/dashboard/', fetch_redirect_response=False)

    def test_profile_username_change_rejects_duplicates(self):
        self.signup()
        User.objects.create_user(username='reserved_name', email='other@example.com', password=self.password)
        duplicate = self.client.post('/profile/', {
            'username': 'RESERVED_NAME', 'first_name': 'Launch', 'last_name': 'Owner',
        })
        self.assertEqual(duplicate.status_code, 200)
        self.assertContains(duplicate, 'already taken')

        changed = self.client.post('/profile/', {
            'username': 'new_launch_name', 'first_name': 'Launch', 'last_name': 'Owner',
        })
        self.assertRedirects(changed, '/profile/', fetch_redirect_response=False)
        user = User.objects.get(email='launch@example.com')
        self.assertEqual(user.username, 'new_launch_name')
        self.assertEqual(user.get_full_name(), 'Launch Owner')

    def test_password_change_and_account_deletion_require_current_password(self):
        self.signup()
        changed = self.client.post('/accounts/password/change/', {
            'oldpassword': self.password,
            'password1': 'Even-stronger-password-271!',
            'password2': 'Even-stronger-password-271!',
        })
        self.assertRedirects(changed, '/profile/', fetch_redirect_response=False)
        user = User.objects.get(username='launch_user')
        self.assertTrue(user.check_password('Even-stronger-password-271!'))

        rejected = self.client.post('/account/delete/', {
            'confirmation': 'launch_user', 'password': 'wrong-password',
        })
        self.assertRedirects(rejected, '/profile/', fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

        deleted = self.client.post('/account/delete/', {
            'confirmation': 'launch_user', 'password': 'Even-stronger-password-271!',
        })
        self.assertRedirects(deleted, '/', fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(pk=user.pk).exists())

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_forgot_password_sends_non_enumerating_reset_email(self):
        self.signup()
        self.client.post('/accounts/logout/')
        response = self.client.post('/accounts/password/reset/', {'email': 'launch@example.com'})
        self.assertRedirects(response, '/accounts/password/reset/done/', fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('password', mail.outbox[0].subject.lower())

    def test_google_button_only_appears_when_provider_is_configured(self):
        login = self.client.get('/accounts/login/')
        self.assertNotContains(login, 'Continue with Google')

        site, _ = Site.objects.update_or_create(id=1, defaults={'domain': 'testserver', 'name': 'Test'})
        app = SocialApp.objects.create(
            provider='google', name='Google', client_id='test-client', secret='test-secret',
        )
        app.sites.add(site)
        configured_login = self.client.get('/accounts/login/')
        self.assertContains(configured_login, 'Continue with Google')
        self.assertContains(configured_login, '/accounts/google/login/')

    def test_social_app_command_is_idempotent_and_disables_missing_credentials(self):
        credentials = {
            'GOOGLE_CLIENT_ID': 'test-google-client',
            'GOOGLE_CLIENT_SECRET': 'test-google-secret',
            'GITHUB_CLIENT_ID': '',
            'GITHUB_CLIENT_SECRET': '',
            'SITE_DOMAIN': 'testserver',
            'SITE_NAME': 'Linkify Test',
        }
        with patch.dict(os.environ, credentials, clear=False):
            call_command('configure_social_apps', verbosity=0)
            call_command('configure_social_apps', verbosity=0)
        site = Site.objects.get(pk=1)
        self.assertEqual(SocialApp.objects.filter(provider='google', sites=site).count(), 1)

        credentials.update({'GOOGLE_CLIENT_ID': '', 'GOOGLE_CLIENT_SECRET': ''})
        with patch.dict(os.environ, credentials, clear=False):
            call_command('configure_social_apps', verbosity=0)
        self.assertFalse(SocialApp.objects.filter(provider='google', sites=site).exists())
