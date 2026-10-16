"""Use the configured TMDB key to verify real searches and process-local cache hits."""
import asyncio
import os
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

from api.core import fetch_media_links
from api.utils import fetch_json


async def verify():
    for query, media in [('Inception', 'movie'), ('Breaking Bad', 'tv')]:
        with patch('api.core.fetch_json', wraps=fetch_json) as provider:
            started = perf_counter()
            first = await fetch_media_links(query, media)
            elapsed = perf_counter() - started
            assert 'Error' not in first, first.get('Error')
            before = provider.await_count
            started = perf_counter()
            second = await fetch_media_links(query.upper(), media)
            cached_elapsed = perf_counter() - started
            assert first == second
            assert provider.await_count == before, 'Repeat query made an upstream request'
            assert first['IMDb Link'], 'External IMDb ID missing'
            print(f'PASS {query}: {first["Official Title"]}; initial={elapsed:.3f}s; cache={cached_elapsed:.3f}s; extra TMDB calls=0', flush=True)


asyncio.run(verify())
