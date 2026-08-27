import asyncio
import aiohttp
from difflib import SequenceMatcher
from decouple import config
from .utils import slugify, fetch_json, head_exists

TMDB_API_KEY = config("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

CACHE = {}

def rank_candidates(results, query):
    """
    Ranks TMDB search candidates based on title similarity, vote count,
    popularity, and presence of poster/metadata. Rejects zero-vote junk results.
    """
    query_clean = query.lower().strip()
    candidates = []
    
    for item in results:
        title = (item.get("title") or item.get("name") or "").strip()
        if not title:
            continue
            
        title_clean = title.lower()
        vote_count = item.get("vote_count", 0)
        popularity = item.get("popularity", 0.0)
        has_poster = 1 if item.get("poster_path") else 0

        sim = SequenceMatcher(None, query_clean, title_clean).ratio()
        
        # Immediate rejection of junk/unverified entries:
        if vote_count == 0 and not has_poster and sim < 0.6:
            continue
            
        score = (sim * 100) + (min(vote_count, 1000) / 10) + (popularity * 2) + (has_poster * 15)
        
        if title_clean == query_clean:
            score += 50
        elif title_clean.startswith(query_clean):
            score += 25
            
        candidates.append((score, item))
        
    if not candidates:
        return None
        
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]

async def fetch_tmdb_data(title: str, media: str, session):
    search_url = f"{TMDB_BASE_URL}/search/{media}"
    search = await fetch_json(
        session,
        search_url,
        {"api_key": TMDB_API_KEY, "query": title}
    )

    if not search or not isinstance(search, dict) or not search.get("results"):
        return None

    item = rank_candidates(search["results"], title)
    if not item:
        return None

    tmdb_id = item["id"]

    details_url = f"{TMDB_BASE_URL}/{media}/{tmdb_id}"
    credits_url = f"{details_url}/credits"

    details, credits = await asyncio.gather(
        fetch_json(session, details_url, {"api_key": TMDB_API_KEY}),
        fetch_json(session, credits_url, {"api_key": TMDB_API_KEY})
    )

    if not details or not isinstance(details, dict):
        return None

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
        
    imdb_id = details.get("imdb_id")
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
        "cast": "Top Cast font-medium",
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
    media = normalize_media_type(media)
    country_code = (country or "us").strip().lower()
    
    cache_key = f"{title}_{media}_{country_code}"
    if cache_key in CACHE:
        return CACHE[cache_key]

    async with aiohttp.ClientSession() as session:
        data = await fetch_tmdb_data(title, media, session)
        
        # Smart fallback: if searching 'tv' returns nothing, try 'movie' (and vice versa)
        if not data and media == "tv":
            data = await fetch_tmdb_data(title, "movie", session)
            if data:
                media = "movie"
        elif not data and media == "movie":
            data = await fetch_tmdb_data(title, "tv", session)
            if data:
                media = "tv"

        if not data:
            return {"Error": f"No verified movie or TV show found matching '{title}'."}

        rt_type = "m" if media == "movie" else "tv"
        rt_url = f"https://www.rottentomatoes.com/{rt_type}/{data['slug']}"
        rt_final = rt_url if await head_exists(session, rt_url) else "RT page not found"

        result = {
            **{k: v for k, v in data.items() if k != "slug"},
            "Rotten Tomatoes": rt_final,
            "Metacritic": f"https://www.metacritic.com/search/{media}/{data['slug']}/results",
            "Letterboxd": f"https://letterboxd.com/film/{data['slug']}/" if media == "movie" else None,
            f"JustWatch ({country_code.upper()})": f"https://www.justwatch.com/{country_code}/search?q={title}"
        }

        CACHE[cache_key] = result
        return result