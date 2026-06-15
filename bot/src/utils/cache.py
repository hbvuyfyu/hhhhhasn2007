import time
import threading
from typing import Any, Optional

from src.config import CACHE_TTL

_cache: dict = {}
_cache_lock = threading.Lock()


def cache_get(key: str) -> Optional[Any]:
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        value, timestamp = entry
        if time.time() - timestamp > CACHE_TTL:
            del _cache[key]
            return None
        return value


def cache_set(key: str, value: Any) -> None:
    with _cache_lock:
        _cache[key] = (value, time.time())


def cache_clear(pattern: str = "") -> None:
    with _cache_lock:
        if pattern:
            keys_to_delete = [k for k in _cache if pattern in k]
            for k in keys_to_delete:
                del _cache[k]
        else:
            _cache.clear()
