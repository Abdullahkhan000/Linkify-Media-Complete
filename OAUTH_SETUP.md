# Google and GitHub login/signup

Both providers use the same button for signup and login: a first successful
authorization creates an account; subsequent authorizations sign in to it.
Sign out ends the Linkify session. It leaves the Google/GitHub session intact.

## Credentials to add

Add these four values to the root `.env` file, then restart Django:

```env
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
```

Credentials load directly from `.env`; no admin or setup command is needed.
Existing database SocialApps are used when environment credentials are absent.
When both exist, the environment credentials take precedence.

## Google

Open [Google Auth Platform](https://console.cloud.google.com/auth/clients).
Select a project, configure branding and audience, and create a **Web application**
OAuth client. If using testing mode, add the accounts you will test with under
test users. Copy the generated client ID and secret into `.env`.

Authorized redirect URI:

```text
http://localhost:8000/accounts/google/login/callback/
```

## GitHub

Open [New OAuth App](https://github.com/settings/applications/new).
Set the homepage URL to `http://localhost:8000` and the authorization callback URL to:

```text
http://localhost:8000/accounts/github/login/callback/
```

Register the app, copy its client ID, generate a client secret, and put both into
`.env`. Use separate OAuth Apps for local development and production: GitHub
OAuth Apps support one callback URL.

## Run and verify

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Open `http://localhost:8000/accounts/signup/` or `/accounts/login/` and select a
provider. Successful authorization redirects to `/dashboard/`. Sign out, then
use the same provider again to check repeat login.

Keep `ACCOUNT_EMAIL_VERIFICATION=none` for the current local setup. Mandatory
verification can be enabled once email delivery is configured.

For Docker, recreate the web container after changing `.env`:

```sh
docker compose up --build -d
```

For production, register the callback paths above with your actual HTTPS domain.
The callback must match the host you use in the browser, including scheme, port,
and trailing slash. Keep secrets in `.env` on the server.

References: [allauth provider configuration](https://docs.allauth.org/en/dev/socialaccount/provider_configuration.html),
[Google web OAuth](https://developers.google.com/identity/protocols/oauth2/web-server),
[GitHub OAuth Apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app).
