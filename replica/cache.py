from __future__ import annotations
import time
from collections import OrderedDict
from typing import Any, Dict, Optional

DEFAULT_MAX_ENTRIES = 1000


class Cache:
    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        self._store: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._max_entries = max_entries

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if not entry:
            return None
        if time.monotonic() > entry["expires"]:
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)  # LRU: mark as recently used
        return entry["value"]

    def put(self, key: str, value: Any, ttl: int) -> None:
        if ttl <= 0:
            return
        self._store[key] = {"value": value, "expires": time.monotonic() + ttl}
        self._store.move_to_end(key)
        while len(self._store) > self._max_entries:
            self._store.popitem(last=False)  # evict oldest

    def clear(self) -> None:
        self._store.clear()
