# Watchlist, favorites and streaming availability

Signed-in users can open `/watchlist/` from desktop/mobile navigation, the console,
or profile settings. Search Movie or TV, save a title, mark favorites, filter the
collection and remove saved titles. The collection is private to the current
account, persists in PostgreSQL, and is deleted when the account is deleted.

Saved title/poster/year/overview metadata is fetched server-side from TMDB.
Clients cannot choose another user or inject a poster URL. Re-saving a title is
idempotent. Movies and shows with the same numeric TMDB ID are separate items.
No user API key or new provider key is needed; the existing `TMDB_API_KEY` is used.

Where to watch displays stream/free/ads/rent/buy providers for a two-letter
country code. Availability is attributed to JustWatch. Provider information can
change; missing country data is displayed honestly, and stale cache data is
labelled. The provided TMDB link opens the actual viewing-options page.

## Deployment

Install the current requirements and apply migrations before deploying new code:

```sh
python manage.py migrate --noinput
npm run build
```

Migration `0012_watchlist` adds a new table and a uniqueness constraint; it does
not modify existing accounts. Vercel and Render should continue using the same
Neon database if both run Django and should share saved collections.

## API

All routes use the signed-in browser session and CSRF protection for writes;
personal API-key authentication is not used for this private account feature.

- `GET/POST /api/v1/watchlist/`: list or save `{tmdb_id, media_type, favorite?}`.
- `GET /api/v1/watchlist/?favorite=true&page=2`: Favorites and pagination.
- `PATCH /api/v1/watchlist/<id>/`: `{favorite: true}`.
- `DELETE /api/v1/watchlist/<id>/`: remove your own item.
- `GET /api/v1/watchlist/search/?q=Inception&type=movie`: find titles.
- `GET /api/v1/watchlist/providers/movie/27205/?country=US`: availability.

Automated tests cover account isolation, CSRF, canonical metadata, idempotency,
Favorites, pagination, deletion and provider failures. The browser verification
script uses an isolated local database and real TMDB search/availability.
