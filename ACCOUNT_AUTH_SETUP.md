# Linkify Media Account Authentication Setup

This bundle adds Google and GitHub sign-in, mandatory email verification, Resend delivery, password change and reset, profile editing, logout, and confirmed account deletion. The changes are intentionally left unpushed.

## Files to copy into the repository

Copy the files while preserving their paths:

| File | Destination | Purpose |
|---|---|---|
| `api/adapters.py` | `api/adapters.py` | Resend-backed allauth email adapter with console fallback |
| `api/views.py` | `api/views.py` | Verification resend and secure account deletion views |
| `api/urls.py` | `api/urls.py` | Named account-security routes |
| `core/settings.py` | `core/settings.py` | Mandatory verification and Google/GitHub provider settings |
| `requirements.txt` | `requirements.txt` | PyJWT and cryptography dependencies for social auth |
| `.env.example` | `.env.example` | OAuth, Resend, and verification configuration placeholders |
| `templates/account/social_buttons.html` | same path | Reusable Google/GitHub buttons |
| `templates/account/login.html` | same path | Social buttons on sign-in |
| `templates/account/signup.html` | same path | Social buttons on signup |
| `templates/account/email/*` | same path | Branded Resend verification emails |
| `templates/account/email_confirm.html` | same path | Branded confirmation screen |
| `templates/account/verification_sent.html` | same path | Verification-sent screen |
| `templates/profile.html` | same path | Profile editing, verification resend, deletion form |

The existing `core/urls.py`, `api/models.py`, `api/admin.py`, and migration files must also include the support-bot changes already present in this working copy. If copying into the same repository, keep those current files and copy the updated versions from the bundle.

## Environment configuration

Copy the example file and fill in the values:

```bash
cp .env.example .env
```

Set the following values in `.env`:

```env
ACCOUNT_EMAIL_VERIFICATION=mandatory
RESEND_API_KEY=re_xxxxxxxxx
DEFAULT_FROM_EMAIL=support@your-verified-domain.com

GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
```

The app does not require the AI support-bot key for account authentication. `OPENAI_API_KEY` can remain empty until the support bot is enabled.

## Google OAuth application

Create a Web application OAuth client in Google Cloud Console. Add this callback URL for local development:

```text
http://localhost:8000/accounts/google/login/callback/
```

For production, add the HTTPS callback URL for the real domain. Put the client ID and secret into `.env`.

## GitHub OAuth application

Create an OAuth App in GitHub Developer Settings. Add this callback URL for local development:

```text
http://localhost:8000/accounts/github/login/callback/
```

For production, add the HTTPS callback URL for the real domain. Put the client ID and secret into `.env`.

## Resend setup

Create a Resend API key and verify the sending domain used in `DEFAULT_FROM_EMAIL`. Until a Resend key is configured, local development falls back to Django’s console email backend, so verification links appear in the server output instead of being delivered.

## Run with Docker

```bash
docker compose up --build -d
docker compose logs -f web
```

The container automatically applies migrations and collects static files before starting Gunicorn.

## Included account flows

Users can sign in or register with email, Google, or GitHub; receive mandatory email verification; request a password reset; change their password from the profile area; edit their first and last name; resend verification; log out; and permanently delete the account after confirming their email and password. Social-only accounts do not have a local password, so the password field is not required during deletion.

## Validation completed

The working copy passed `python manage.py check`, migration generation checks, account-page smoke tests for login/signup/password reset, and the support-bot test suite. No Git commit or push was performed for these authentication changes.
