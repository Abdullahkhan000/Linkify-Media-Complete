# Media search caching and reliability

No extra media API is required. TMDB remains the data provider.

Search normalizes whitespace, Unicode and case for cache identity. Batch calls
deduplicate matching queries while retaining result order and each item's fields.
Search details append credits and external IDs in one TMDB call, reducing a new
successful lookup to two upstream calls. TV IMDb links use TMDB's external IDs.
Exact localized/original title matches take priority over unrelated popularity.
Rotten Tomatoes links open a title search; no slow HEAD request or guessed title
page is needed to return valid TMDB data.

Defaults, overridable in the deployment environment:

```env
TMDB_CACHE_TTL=900
MEDIA_CACHE_TTL=3600
MEDIA_STALE_CACHE_TTL=86400
MEDIA_NOT_FOUND_CACHE_TTL=60
```

Successful results are fresh for their TTL. A separate last-good copy can be
returned during a provider outage until the stale TTL expires. Such responses
include `_cache: {"status": "stale", "reason": "provider_unavailable"}`.
Provider errors are not cached as missing titles. An uncached provider failure
returns HTTP 503; only a genuine successful search with no matching title returns
404, with a short negative-cache TTL. All retries fit within the request deadline.
Long Retry-After delays return promptly instead of retrying before that delay.
Cache connection failures bypass the cache rather than failing a valid search.

Without `REDIS_URL`, Django uses per-process memory. Warm processes benefit, but
Vercel cold starts and separate workers do not share this cache. For shared cache
behavior, set the existing `REDIS_URL` setting to a reachable Redis instance using
a Redis connection URL; the code does not require a new media API key.

Verification: `python scripts/verify_media_cache.py` uses the existing TMDB key
without printing it, performs movie and TV searches, and verifies that a repeated
query makes zero additional upstream calls. Automated tests simulate outages,
malformed responses, expired caches, field filtering and duplicate batch items.
