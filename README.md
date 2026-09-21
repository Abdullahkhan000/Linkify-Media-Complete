# Linkify Media

Linkify Media is a Next.js + Django REST Framework SaaS starter for TMDB-backed movie and TV metadata. The primary product UI is a responsive Next.js 16 app; Django, DRF and django-allauth provide the secure data and account layer.

## What is implemented

- TMDB movie and TV title lookup with metadata enrichment and one-hour Redis/local cache.
- Versioned `/api/v1/` endpoints plus an OpenAPI 3.1 schema and Swagger UI.
- API secrets hashed at rest, one-time secret display, scopes, expiry, revocation, and rotation.
- Atomic daily quotas, per-minute limits, request status/latency logs, charts, and CSV export.
- Short-lived signed browser-demo tokens with per-IP limits; there is no hardcoded demo API key.
- Username/email login, signup, password recovery, profile editing, account deletion, and optional Google/GitHub sign-in.
- A colorful, animated Next.js workspace with a same-origin backend-for-frontend proxy; Django templates remain available as complete auth/email fallbacks.
- Email verification is disabled by default for launch and can later be enabled with one environment setting.
- LemonSqueezy checkout, signed/idempotent webhooks, subscription downgrades, and customer portal access.
- Docker deployment, SQLite for local development, optional PostgreSQL, optional Redis, and health/readiness endpoints.

Linkify currently uses TMDB as its metadata provider. IMDb, Rotten Tomatoes, Metacritic, Letterboxd, and JustWatch values are outbound links, not independently aggregated datasets.

## Requirements

- Python 3.12
- Node.js 24 and npm 11
- Docker 20.10+ for the container workflow
- A TMDB key for live media search (the rest of the site boots safely without one)

## Local setup

```bash
git clone https://github.com/Brayanfury007/my-linkify.git
cd my-linkify
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
npm ci
npm run build:css
cd frontend
npm ci
cp .env.example .env.local
npm run build
cd ..
cp .env.example .env
python manage.py migrate
python manage.py configure_social_apps
python manage.py runserver 8000
```

In a second terminal, run `cd frontend && npm run dev`, then open <http://localhost:3000/>. Django runs at <http://localhost:8000/> and Swagger remains available at <http://localhost:8000/api/docs/>.

## Docker

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
docker compose logs -f web
```

Open <http://localhost:3000/>. The `frontend` container proxies only approved Django routes to the internal `web` service, keeping browser session cookies same-origin.

The web readiness endpoint is `/api/ready/`. Stop the stack with `docker compose down`.

## Configuration

Use `.env.example` as the complete non-secret template. Important production values are:

```ini
SECRET_KEY=a-long-random-production-secret
DEBUG=False
ALLOWED_HOSTS=api.example.com
CSRF_TRUSTED_ORIGINS=https://api.example.com
FRONTEND_URL=https://app.example.com
DATABASE_URL=postgresql://user:password@host:5432/database
REDIS_URL=redis://redis:6379/0
TMDB_API_KEY=your-tmdb-key

LEMONSQUEEZY_API_KEY=your-api-key
LEMONSQUEEZY_STORE_ID=your-store-id
LEMONSQUEEZY_VARIANT_PRO=your-pro-variant-id
LEMONSQUEEZY_VARIANT_BIZ=your-business-variant-id
LEMONSQUEEZY_WEBHOOK_SECRET=your-webhook-secret
```

When `DEBUG=False`, `SECRET_KEY` is mandatory and secure cookies, HTTPS redirect, and HSTS default to enabled. If TLS redirects are handled outside Django, override the relevant settings explicitly and deliberately.

OAuth provider credentials are loaded into django-allauth `SocialApp` records by `python manage.py configure_social_apps`, which the Docker entrypoint runs after migrations.

For local Google sign-in, set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SITE_DOMAIN=localhost:8000`, and `FRONTEND_URL=http://localhost:3000`, then run `python manage.py configure_social_apps`. Register this exact authorized redirect URI in Google Cloud:

```text
http://localhost:8000/accounts/google/login/callback/
```

Production must use the matching HTTPS domain. If credentials are absent, social buttons stay hidden instead of opening a broken OAuth flow. `ACCOUNT_EMAIL_VERIFICATION=none` is the launch default; change it to `mandatory` only after outbound mail and your public domain are ready.

## API

Send credentials only through the `X-API-Key` header. Query-string keys are intentionally unsupported because URLs commonly leak into logs and browser history.

### Search

```bash
curl "http://localhost:8000/api/v1/search/?q=Inception&type=movie&country=us" \
  -H "X-API-Key: lm_live_your_secret"
```

Optional `fields` aliases include `title`, `year`, `genres`, `runtime`, `rating`, `poster`, `cast`, `tmdb`, `imdb`, and `justwatch`.

For discovery workflows, use:

- `GET /api/v1/search/results/?q=Dune&type=movie&page=1&year=2021` for paginated results.
- `GET /api/v1/media/movie/438631/?country=US` for details, cast, recommendations, and watch providers.
- `GET /api/v1/trending/?type=all` for weekly trending media.
- `GET /api/v1/people/search/?q=Denis%20Villeneuve` for cast and creator search.

### Batch

```bash
curl -X POST "http://localhost:8000/api/v1/batch/" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: lm_live_your_secret" \
  -d '{"items":[{"q":"Dune","type":"movie"},{"q":"The Bear","type":"tv"}]}'
```

Batch requires the `batch` scope and a Pro or Business plan. Limits are 25 and 100 items respectively; the browser demo allows 3.

### Usage

```bash
curl "http://localhost:8000/api/v1/usage/" \
  -H "X-API-Key: lm_live_your_secret"
```

API keys are shown only once. Store them in a server-side secret manager or environment variable, never in browser JavaScript or source control.

Starter clients are included in `sdk/python/linkify.py` and `sdk/javascript/linkify.mjs`. An importable collection is available at `postman/Linkify_Media.postman_collection.json`.

## Operations and checks

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py check --deploy
```

- Liveness: `GET /api/health/`
- Readiness: `GET /api/ready/`
- OpenAPI schema: `GET /api/schema/`
- Swagger UI: `GET /api/docs/`

## License

[MIT](LICENSE)
