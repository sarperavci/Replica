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
    REPLACEMENTS: List[dict]
    STATIC_EXTENSIONS: List[str]
    CACHE_TTL_STATIC: int
    CACHE_TTL_HTML: int
    INJECT_JS: str
    INJECT_JS_FILE: str

    # Default origin used only as an internal fallback when a request does not provide
    # a Host header. This is not configurable via environment variables anymore.
    _DEFAULT_ORIGIN = "http://127.0.0.1:8000"

    def __init__(self) -> None:
        self.TARGET_ORIGIN = os.getenv("TARGET_ORIGIN", "https://example.com")

        raw = os.getenv("REPLACEMENTS", "")
        if raw:
            try:
                self.REPLACEMENTS = json.loads(raw)
            except Exception:
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
        # Optional inline JavaScript to inject into HTML responses (string).
        # If provided, this string will be wrapped in <script>...</script> and
        # inserted before the closing </body> tag (or appended if no closing tag).
        self.INJECT_JS = os.getenv("INJECT_JS", "")
        # Optional path to a JS file to load instead of INJECT_JS variable.
        self.INJECT_JS_FILE = os.getenv("INJECT_JS_FILE", "")
        if self.INJECT_JS_FILE:
            try:
                with open(self.INJECT_JS_FILE, "r", encoding="utf-8") as fh:
                    self.INJECT_JS = fh.read()
            except Exception:
                # Ignore failures and fall back to env var
                self.INJECT_JS = os.getenv("INJECT_JS", "")
    @property
    def target_host(self) -> str:
        return urlparse(self.TARGET_ORIGIN).netloc

    @property
    def my_host(self) -> str:
        """Return a fallback host (netloc) to use when a request lacks a Host header.

        This uses a hardcoded default origin rather than an environment-provided one.
        """
        return urlparse(self._DEFAULT_ORIGIN).netloc


# Single settings instance for modules to import
settings = Settings()
