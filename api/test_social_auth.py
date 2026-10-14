from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from allauth.account.models import EmailAddress
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialLogin
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.test import Client, TestCase, override_settings


PROVIDERS = {
    'google': {'SCOPE': ['profile', 'email'], 'APP': {
        'client_id': 'google-client', 'secret': 'google-secret', 'key': '',
    }},
    'github': {'SCOPE': ['user:email'], 'APP': {
        'client_id': 'github-client', 'secret': 'github-secret', 'key': '',
    }},
}


@override_settings(SOCIALACCOUNT_PROVIDERS=PROVIDERS, ACCOUNT_EMAIL_VERIFICATION='none')
class SocialAuthTests(TestCase):
    def test_both_buttons_available_on_login_and_signup_without_database_apps(self):
        for path in ('/accounts/login/', '/accounts/signup/'):
            response = self.client.get(path)
            for provider in PROVIDERS:
                self.assertContains(response, f'Continue with {provider.title()}'.replace('Github', 'GitHub'))
                self.assertContains(response, f'/accounts/{provider}/login/')
                self.assertContains(response, 'method="post"')

    def test_environment_credentials_take_precedence_over_database_apps(self):
        site = Site.objects.get(pk=1)
        for provider in PROVIDERS:
            stale_app = SocialApp.objects.create(
                provider=provider, client_id='stale-client', secret='stale-secret',
            )
            stale_app.sites.add(site)
            app = get_adapter().get_app(None, provider)
            self.assertEqual(app.client_id, f'{provider}-client')
            self.assertIsNone(app.pk)

    def test_provider_signup_repeat_login_and_logout(self):
        adapters = {
            'google': 'allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter',
            'github': 'allauth.socialaccount.providers.github.views.GitHubOAuth2Adapter',
        }
        for provider, adapter in adapters.items():
            with self.subTest(provider=provider):
                for attempt in range(2):
                    start = self.client.post(f'/accounts/{provider}/login/')
                    self.assertEqual(start.status_code, 302)
                    query = parse_qs(urlparse(start['Location']).query)
                    self.assertEqual(query['client_id'], [f'{provider}-client'])
                    self.assertEqual(query['redirect_uri'], [
                        f'http://testserver/accounts/{provider}/login/callback/',
                    ])
                    email = f'{provider}@example.com'
                    login = SocialLogin(
                        provider=get_adapter().get_provider(None, provider),
                        user=get_user_model()(email=email),
                        account=SocialAccount(provider=provider, uid='12345'),
                        email_addresses=[EmailAddress(email=email, verified=True, primary=True)],
                    )
                    with patch(f'{adapter}.get_access_token_data', return_value={'access_token': 'test-token'}), patch(
                        f'{adapter}.complete_login', return_value=login,
                    ):
                        callback = self.client.get(f'/accounts/{provider}/login/callback/', {
                            'code': 'test-code', 'state': query['state'][0],
                        })
                    self.assertRedirects(callback, '/dashboard/', fetch_redirect_response=False)
                    self.assertIn('_auth_user_id', self.client.session)
                    self.assertEqual(get_user_model().objects.filter(email=email).count(), 1)
                    self.assertRedirects(self.client.post('/accounts/logout/'), '/', fetch_redirect_response=False)
                    self.assertNotIn('_auth_user_id', self.client.session)

    def test_social_login_and_logout_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        for provider in PROVIDERS:
            self.assertEqual(client.post(f'/accounts/{provider}/login/').status_code, 403)
        user = get_user_model().objects.create_user(username='csrf-user')
        client.force_login(user)
        self.assertEqual(client.post('/accounts/logout/').status_code, 403)
        self.assertIn('_auth_user_id', client.session)

    def test_callback_rejects_missing_state(self):
        for provider in PROVIDERS:
            response = self.client.get(f'/accounts/{provider}/login/callback/', {'code': 'untrusted'})
            self.assertEqual(response.status_code, 401)
            self.assertNotIn('_auth_user_id', self.client.session)
            self.assertFalse(SocialAccount.objects.exists())
