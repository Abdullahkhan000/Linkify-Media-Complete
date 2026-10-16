"""Best-effort media caching: Redis failures must not break provider requests."""
from copy import deepcopy
import hashlib
import json
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)


def cache_key(namespace, identity):
    payload = json.dumps(identity, sort_keys=True, ensure_ascii=True)
    return f'{namespace}:v2:{hashlib.sha256(payload.encode()).hexdigest()}'


async def read(key):
    try:
        return deepcopy(await cache.aget(key))
    except Exception as exc:
        logger.warning('Media cache read unavailable (%s).', type(exc).__name__)
        return None


async def write(key, value, ttl, stale_ttl=None):
    try:
        await cache.aset(key, deepcopy(value), timeout=ttl)
        if stale_ttl is not None:
            await cache.aset(key + ':stale', deepcopy(value), timeout=max(ttl, stale_ttl))
    except Exception as exc:
        logger.warning('Media cache write unavailable (%s).', type(exc).__name__)
