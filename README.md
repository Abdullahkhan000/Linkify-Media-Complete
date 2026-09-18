# Linkify Media

Linkify Media is a Django and Django REST Framework SaaS starter for TMDB-backed movie and TV metadata. It includes verified accounts, hashed and scoped API keys, quota enforcement, usage analytics, LemonSqueezy billing hooks, support tickets, a browser demo, and a developer dashboard.

## What is implemented

- TMDB movie and TV title lookup with metadata enrichment and one-hour Redis/local cache.
- Versioned `/api/v1/` endpoints plus an OpenAPI 3.1 schema and Swagger UI.
- API secrets hashed at rest, one-time secret display, scopes, expiry, revocation, and rotation.
- Atomic daily quotas, per-minute limits, request status/latency logs, charts, and CSV export.
- Short-lived signed browser-demo tokens with per-IP limits; there is no hardcoded demo API key.
- Mandatory email verification before key creation, Google/GitHub sign-in support, and Resend delivery.
- LemonSqueezy checkout, signed/idempotent webhooks, subscription downgrades, and customer portal access.
- Docker deployment, SQLite for local development, optional PostgreSQL, optional Redis, and health/readiness endpoints.

Linkify currently uses TMDB as its metadata provider. IMDb, Rotten Tomatoes, Metacritic, Letterboxd, and JustWatch values are outbound links, not independently aggregated datasets.

## Requirements

- Python 3.12
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
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. Swagger UI is available at <http://127.0.0.1:8000/api/docs/>.

## Docker

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
docker compose logs -f web
```

The web readiness endpoint is `/api/ready/`. Stop the stack with `docker compose down`.

## Configuration

Use `.env.example` as the complete non-secret template. Important production values are:

```ini
SECRET_KEY=a-long-random-production-secret
DEBUG=False
ALLOWED_HOSTS=api.example.com
CSRF_TRUSTED_ORIGINS=https://api.example.com
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
