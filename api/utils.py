import re
import asyncio

import aiohttp

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text

async def fetch_json(session, url, params=None):
    for attempt in range(3):
        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 429 or resp.status >= 500:
                    if attempt < 2:
                        await asyncio.sleep(0.25 * (2 ** attempt))
                        continue
                    return None
                if resp.status >= 400:
                    return None
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            if attempt == 2:
                return None
            await asyncio.sleep(0.25 * (2 ** attempt))
    return None

async def head_exists(session, url):
    try:
        async with session.head(url, allow_redirects=True, timeout=5) as r:
            return r.status == 200
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return False
