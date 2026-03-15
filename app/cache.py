import time
from typing import Any


class TTLCache:
    def __init__(self):
        self._storage: dict[str, tuple[float, Any]] = {}

    def get(self, key: str):
        item = self._storage.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at < time.time():
            self._storage.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int = 60):
        self._storage[key] = (time.time() + ttl_seconds, value)

    def delete_prefix(self, prefix: str):
        for key in list(self._storage.keys()):
            if key.startswith(prefix):
                self._storage.pop(key, None)


cache = TTLCache()
