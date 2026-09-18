# Linkify Media Branded Authentication Templates

The repository now overrides the default django-allauth account and socialaccount screens. These files must remain at the exact paths shown below so Django template discovery uses them instead of package defaults.

## Social OAuth templates

| Path | Purpose |
|---|---|
| `templates/socialaccount/login.html` | Google/GitHub authorization confirmation screen |
| `templates/socialaccount/login_redirect.html` | Branded automatic provider redirect screen |
| `templates/socialaccount/signup.html` | Complete profile after social signup |
| `templates/socialaccount/authentication_error.html` | OAuth failure screen |
| `templates/socialaccount/login_cancelled.html` | OAuth cancellation screen |
| `templates/socialaccount/connections.html` | Connected provider management |
| `templates/socialaccount/base_entrance.html` | Prevents default allauth entrance shell |
| `templates/socialaccount/base_manage.html` | Prevents default allauth management shell |
| `templates/socialaccount/snippets/provider_list.html` | Reusable provider buttons |
| `templates/socialaccount/snippets/login_extra.html` | Branded social-login separator/buttons |

## Account templates

The existing `templates/account/login.html` and `templates/account/signup.html` include Google and GitHub buttons. The bundle also includes branded logout, email confirmation, verification-sent, password change, password reset, password reset completion, password reset-from-key, password reset-from-key completion, password set, reauthentication, email change, inactive-account, and verified-email-required pages.

## Why `/accounts/google/login/` previously showed a plain page

Current django-allauth displays a provider confirmation/redirect screen before sending the browser to Google. The override at `templates/socialaccount/login.html` is the page that replaces that default confirmation screen. The override at `templates/socialaccount/login_redirect.html` replaces the short auto-redirect page.

## Required provider setup

The provider credentials still need to exist either in the database as `SocialApp` records associated with the active Site, or through the environment-backed provider configuration supported by the installed allauth version. The most reliable setup is Django Admin:

```text
/admin/socialaccount/socialapp/
```

Add one Google app and one GitHub app, select the active Site, and keep the callback URLs exact:

```text
http://localhost:8000/accounts/google/login/callback/
http://localhost:8000/accounts/github/login/callback/
```

## Validation

The working copy passed Django checks. Login, signup, password reset, Google login, and GitHub login routes returned HTTP 200, and the Google/GitHub pages contained the new branded content. No Git commit or push was performed for these template changes.
