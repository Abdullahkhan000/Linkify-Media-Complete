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
# Watch progress

## Recommendations and collection tools

**Picked for you** uses TMDB recommendations from up to three favorites or titles rated 8/10 or higher. Suggestions include the source title, omit existing saved entries, and are deduplicated by media type and TMDB ID. Use **Refresh recommendations** after changing favorites or ratings. Suggestions support saving, favorites, removal, and country-specific viewing options.

`GET /api/v1/watchlist/recommendations/` requires a signed-in session and has the existing media-request throttle. Provider responses use the existing cache; partial/stale results are labelled. No new API key, environment variable, or migration is needed for these additions.

The collection supports `q` (title, up to 200 characters) and `sort` (`newest`, `oldest`, `title`, `rating`). Search, status, and Favorites combine before pagination; `matched` reports the filtered count. Personal ratings sort highest first with unrated entries last. The UI provides an Apply button and sorting selector.

Provider references: [movie recommendations](https://developer.themoviedb.org/reference/movie-recommendations), [TV recommendations](https://developer.themoviedb.org/reference/tv-series-recommendations).

Saved titles default to **Plan to watch**. Users can change this to **Watching** or **Watched**, save an optional personal rating from 1–10, and keep up to 1,000 characters of private notes. The collection status filter combines with Favorites. Use **Save progress** to persist edits. Clear the rating with **Not rated**.

Migration `0013_watchlist_progress` adds these fields. The existing session authentication, CSRF protection, and per-user ownership checks also protect progress and notes.
