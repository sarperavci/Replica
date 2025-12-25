from __future__ import annotations
import time
from typing import Any, Dict, Optional


class Cache:
    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self._store.get(key)
        if not entry:
            return None
        if time.time() > entry["expires"]:
            del self._store[key]
            return None
        return entry["value"]

    def put(self, key: str, value: Any, ttl: int) -> None:
        self._store[key] = {"value": value, "expires": time.time() + ttl}

    def clear(self) -> None:
        self._store.clear()
