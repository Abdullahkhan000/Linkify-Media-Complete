import re
import aiohttp

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text

async def fetch_json(session, url, params=None):
    async with session.get(url, params=params, timeout=10) as resp:
        return await resp.json()

async def head_exists(session, url):
    try:
        async with session.head(url, allow_redirects=True, timeout=5) as r:
            return r.status == 200
    except:
        return False