"""Simple environment/settings loader without strict pydantic dependency."""
from __future__ import annotations
from typing import List, Any
import os
import json
from urllib.parse import urlparse


class Settings:
    """Lightweight settings object populated from environment variables.

    This avoids tight coupling to a specific pydantic version while keeping
    configuration convenient via `.env` or environment variables.
    """

    TARGET_ORIGIN: str
    MY_ORIGIN: str
    REPLACEMENTS: List[dict]
    STATIC_EXTENSIONS: List[str]
    CACHE_TTL_STATIC: int
    CACHE_TTL_HTML: int

    def __init__(self) -> None:
        self.TARGET_ORIGIN = os.getenv("TARGET_ORIGIN", "https://example.com")
        self.MY_ORIGIN = os.getenv("MY_ORIGIN", "http://127.0.0.1:8000")

        raw = os.getenv("REPLACEMENTS", "")
        if raw:
            try:
                self.REPLACEMENTS = json.loads(raw)
            except Exception:
                # Fallback: empty list on parse errors
                self.REPLACEMENTS = []
        else:
            self.REPLACEMENTS = []

        self.STATIC_EXTENSIONS = [
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".css",
            ".js",
            ".woff",
            ".woff2",
        ]

        self.CACHE_TTL_STATIC = int(os.getenv("CACHE_TTL_STATIC", "86400"))
        self.CACHE_TTL_HTML = int(os.getenv("CACHE_TTL_HTML", "300"))

    @property
    def target_host(self) -> str:
        return urlparse(self.TARGET_ORIGIN).netloc

    @property
    def my_host(self) -> str:
        return urlparse(self.MY_ORIGIN).netloc


# Single settings instance for modules to import
settings = Settings()
