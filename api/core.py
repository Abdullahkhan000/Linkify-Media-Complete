import asyncio
import aiohttp
import math
import re
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import quote_plus

from django.conf import settings

from .utils import slugify, fetch_json
from .provider_cache import cache_key, read, write

TMDB_BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


class ProviderUnavailable(Exception):
    pass


def normalize_query(title):
    return ' '.join(unicodedata.normalize('NFKC', title).split())


async def cached_tmdb_request(session, path, params=None, ttl=None):
    request_params = {**(params or {}), 'api_key': settings.TMDB_API_KEY}
    key = cache_key('tmdb', [path, request_params])
    cached = await read(key)
    if cached is not None:
        return cached
    result = await fetch_json(session, f'{TMDB_BASE_URL}/{path}', request_params)
    if not isinstance(result, dict) or result.get('success') is False:
        raise ProviderUnavailable()
    if path.startswith(('search/', 'trending/')):
        if not isinstance(result.get('results'), list) or any(not isinstance(item, dict) or not item.get('id') for item in result['results']):
            raise ProviderUnavailable()
    if re.fullmatch(r'(movie|tv)/\d+', path) and (not result.get('id') or not (result.get('title') or result.get('name'))):
        raise ProviderUnavailable()
    effective_ttl = ttl if ttl is not None else settings.TMDB_CACHE_TTL
    if result.get('results') == []:
        effective_ttl = min(effective_ttl, settings.MEDIA_NOT_FOUND_CACHE_TTL)
    await write(key, result, effective_ttl, settings.MEDIA_STALE_CACHE_TTL)
    return result


async def fetch_tmdb_endpoint(path: str, params=None, cache_ttl=None):
    if not settings.TMDB_API_KEY:
        return {"Error": "Media provider is not configured.", "code": "provider_not_configured"}
    safe_path = str(path).strip("/")
    if ".." in safe_path or not safe_path:
        return {"Error": "Invalid provider path.", "code": "invalid_request"}
    key = cache_key('tmdb', [safe_path, {**(params or {}), 'api_key': settings.TMDB_API_KEY}])
    timeout = aiohttp.ClientTimeout(total=settings.API_REQUEST_TIMEOUT)
    try:
        async with asyncio.timeout(settings.API_REQUEST_TIMEOUT):
            async with aiohttp.ClientSession(timeout=timeout) as session:
                return await cached_tmdb_request(session, safe_path, params, cache_ttl)
    except (ProviderUnavailable, TimeoutError):
        stale = await read(key + ':stale')
        if stale is not None:
            return {**stale, '_cache': {'status': 'stale', 'reason': 'provider_unavailable'}}
        return {'Error': 'Media provider is temporarily unavailable. Please retry shortly.', 'code': 'provider_unavailable'}


def summarize_result(item):
    poster = item.get("poster_path") or item.get("profile_path")
    release_date = item.get("release_date") or item.get("first_air_date")
    return {
        "id": item.get("id"),
        "media_type": item.get("media_type"),
        "title": item.get("title") or item.get("name"),
        "release_year": release_date[:4] if release_date else None,
        "overview": item.get("overview"),
        "rating": item.get("vote_average"),
        "poster_url": f"{IMAGE_BASE}{poster}" if poster else None,
    }

def rank_candidates(results, query):
    """
    Ranks TMDB search candidates based on title similarity, vote count,
    popularity, and presence of poster/metadata. Rejects zero-vote junk results.
    """
    clean_title = lambda value: ' '.join(re.sub(r'[^\w\s]', ' ', normalize_query(value).casefold()).split())
    query_clean = clean_title(query)
    candidates = []
    
    for item in results:
        title = (item.get("title") or item.get("name") or "").strip()
        if not title:
            continue
            
        title_clean = clean_title(title)
        original_clean = clean_title(item.get('original_title') or item.get('original_name') or title)
        vote_count = item.get("vote_count") or 0
        popularity = item.get("popularity") or 0.0
        has_poster = 1 if item.get("poster_path") else 0

        sim = max(SequenceMatcher(None, query_clean, candidate).ratio() for candidate in (title_clean, original_clean))
        if sim < 0.4 and query_clean not in title_clean and query_clean not in original_clean:
            continue
        
        # Immediate rejection of junk/unverified entries:
        if vote_count == 0 and not has_poster and sim < 0.6:
            continue
            
        score = (sim * 100) + (min(vote_count, 1000) / 50) + min(math.log1p(max(popularity, 0)) * 4, 20) + (has_poster * 5)
        
        exact = query_clean in (title_clean, original_clean)
        if exact:
            score += 50
        elif title_clean.startswith(query_clean):
            score += 25
            
        candidates.append((exact, score, item))
        
    if not candidates:
        return None
        
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2]

async def fetch_tmdb_data(title: str, media: str, session):
    search = await cached_tmdb_request(session, f'search/{media}', {'query': title, 'include_adult': 'false'})

    if not isinstance(search.get('results'), list):
        raise ProviderUnavailable()
    if not search['results']:
        return None

    item = rank_candidates(search["results"], title)
    if not item:
        return None

    tmdb_id = item["id"]

    details = await cached_tmdb_request(session, f'{media}/{tmdb_id}', {'append_to_response': 'credits,external_ids'})
    credits = details.get('credits') or {}

    if not (details.get('title') or details.get('name')) or details.get('id') != tmdb_id:
        raise ProviderUnavailable()

    official_title = details.get("title") or details.get("name")
    release_date = details.get("release_date") or details.get("first_air_date")
    release_year = release_date[:4] if release_date else None
    runtime = details.get("runtime")
    if not runtime:
        ep = details.get("episode_run_time")
        runtime = ep[0] if ep else None

    poster = details.get("poster_path")
    poster_url = f"{IMAGE_BASE}{poster}" if poster else None
    genres = [g["name"] for g in details.get("genres", [])] if details.get("genres") else []
    
    cast = []
    if credits and isinstance(credits, dict) and credits.get("cast"):
        cast = [c["name"] for c in credits["cast"][:5]]
        
    imdb_id = details.get("imdb_id") or (details.get('external_ids') or {}).get('imdb_id')
    imdb_link = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None

    return {
        "Official Title": official_title,
        "Release Year": release_year,
        "Genres": genres,
        "Runtime (mins)": runtime,
        "TMDB Rating": f'{details.get("vote_average", 0)} ({details.get("vote_count", 0)} votes)',
        "Poster URL": poster_url,
        "Top Cast": cast,
        "TMDB Link": f"https://www.themoviedb.org/{media}/{tmdb_id}",
        "IMDb Link": imdb_link,
        "slug": slugify(official_title)
    }

def normalize_media_type(media: str) -> str:
    if not media:
        return "movie"
    clean = str(media).strip().lower()
    if clean in ["show", "tv", "series", "anime", "tvshow", "tv show"]:
        return "tv"
    return "movie"

def filter_fields(result: dict, fields_param: str) -> dict:
    """
    Filters dictionary result based on comma-separated requested fields (or aliases).
    Example: fields=title,poster,imdb -> returns only Official Title, Poster URL, IMDb Link
    """
    if not fields_param or not isinstance(result, dict) or "Error" in result:
        return result
        
    requested = [f.strip().lower() for f in str(fields_param).split(",") if f.strip()]
    if not requested:
        return result

    ALIAS_MAP = {
        "title": "Official Title",
        "official title": "Official Title",
        "year": "Release Year",
        "release year": "Release Year",
        "genres": "Genres",
        "runtime": "Runtime (mins)",
        "rating": "TMDB Rating",
        "tmdb rating": "TMDB Rating",
        "poster": "Poster URL",
        "poster url": "Poster URL",
        "cast": "Top Cast",
        "top cast": "Top Cast",
        "tmdb": "TMDB Link",
        "tmdb link": "TMDB Link",
        "imdb": "IMDb Link",
        "imdb link": "IMDb Link",
        "rt": "Rotten Tomatoes",
        "rotten tomatoes": "Rotten Tomatoes",
        "metacritic": "Metacritic",
        "letterboxd": "Letterboxd",
    }

    filtered = {}
    for req in requested:
        if req == "justwatch":
            for k, v in result.items():
                if "JustWatch" in k:
                    filtered[k] = v
        else:
            target_key = ALIAS_MAP.get(req)
            if target_key and target_key in result:
                filtered[target_key] = result[target_key]
            else:
                for original_key in result.keys():
                    if original_key.lower() == req:
                        filtered[original_key] = result[original_key]

    return filtered if filtered else result

async def fetch_media_links(title: str, media: str, country: str = "us"):
    if not settings.TMDB_API_KEY:
        return {
            "Error": "Media search is temporarily unavailable because the provider is not configured.",
            "code": "provider_not_configured",
        }

    title = normalize_query(title)
    media = normalize_media_type(media)
    country_code = (country or "us").strip().lower()
    key = cache_key('media', [title.casefold(), media, country_code, settings.TMDB_API_KEY])
    cached_result = await read(key)
    if cached_result is not None:
        return cached_result
    missing = await read(key + ':missing')
    if missing is not None:
        return missing

    timeout = aiohttp.ClientTimeout(total=settings.API_REQUEST_TIMEOUT)
    try:
        async with asyncio.timeout(settings.API_REQUEST_TIMEOUT):
            async with aiohttp.ClientSession(timeout=timeout) as session:
                data = await fetch_tmdb_data(title, media, session)
                # Try the other type only after a genuine successful no-match response.
                if not data:
                    media = 'movie' if media == 'tv' else 'tv'
                    data = await fetch_tmdb_data(title, media, session)
        if not data:
            result = {'Error': f"No verified movie or TV show found matching '{title}'.", 'code': 'not_found'}
            await write(key + ':missing', result, settings.MEDIA_NOT_FOUND_CACHE_TTL)
            return result
        result = {
            **{k: v for k, v in data.items() if k != 'slug'},
            'Rotten Tomatoes': f"https://www.rottentomatoes.com/search?search={quote_plus(data['Official Title'])}",
            'Metacritic': f"https://www.metacritic.com/search/{media}/{data['slug']}/results",
            'Letterboxd': f"https://letterboxd.com/film/{data['slug']}/" if media == 'movie' else None,
            f'JustWatch ({country_code.upper()})': f'https://www.justwatch.com/{country_code}/search?q={quote_plus(title)}',
        }
        await write(key, result, settings.MEDIA_CACHE_TTL, settings.MEDIA_STALE_CACHE_TTL)
        return result
    except (ProviderUnavailable, TimeoutError):
        stale = await read(key + ':stale')
        if stale is not None:
            return {**stale, '_cache': {'status': 'stale', 'reason': 'provider_unavailable'}}
        return {'Error': 'Media provider is temporarily unavailable. Please retry shortly.', 'code': 'provider_unavailable'}
