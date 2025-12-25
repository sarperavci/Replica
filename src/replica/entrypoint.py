"""Docker entrypoint and startup diagnostics for Replica.

This script performs runtime validation of required environment variables and
prints a short diagnostics summary. If validation passes it replaces the current
process with an `uvicorn` server (execv).
"""
from __future__ import annotations

import json
import os
import sys
import logging
from typing import List
from urllib.parse import urlparse

from .config import Settings as _Settings  # type: ignore

logger = logging.getLogger("replica.entrypoint")
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(levelname)s] %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def _is_valid_url(value: str) -> bool:
    if not value:
        return False
    p = urlparse(value)
    return p.scheme in ("http", "https") and bool(p.netloc)


def validate_settings(settings: _Settings) -> List[str]:
    errors: List[str] = []

    if not _is_valid_url(settings.TARGET_ORIGIN):
        errors.append("TARGET_ORIGIN must be a valid http(s) URL")

    if not _is_valid_url(settings.MY_ORIGIN):
        errors.append("MY_ORIGIN must be a valid http(s) URL")

    # Validate REPLACEMENTS if provided in env
    raw = os.getenv("REPLACEMENTS", "")
    if raw:
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                errors.append("REPLACEMENTS must be a JSON list of {from,to} objects")
            else:
                for i, item in enumerate(parsed):
                    if not isinstance(item, dict) or "from" not in item or "to" not in item:
                        errors.append(f"REPLACEMENTS[{i}] must be an object with 'from' and 'to' keys")
        except json.JSONDecodeError:
            errors.append("REPLACEMENTS must be valid JSON")

    # TTLs
    try:
        int(os.getenv("CACHE_TTL_STATIC", "86400"))
    except Exception:
        errors.append("CACHE_TTL_STATIC must be an integer")

    try:
        int(os.getenv("CACHE_TTL_HTML", "300"))
    except Exception:
        errors.append("CACHE_TTL_HTML must be an integer")

    return errors


def print_diagnostics(settings: _Settings) -> None:
    logger.info("Starting Replica — reverse proxy")
    logger.info("TARGET_ORIGIN=%s", settings.TARGET_ORIGIN)
    logger.info("MY_ORIGIN=%s", settings.MY_ORIGIN)
    logger.info("REPLACEMENTS=%d rules", len(settings.REPLACEMENTS or []))
    logger.info("STATIC_EXTENSIONS=%s", ",".join(settings.STATIC_EXTENSIONS))
    logger.info("CACHE_TTL_STATIC=%s", os.getenv("CACHE_TTL_STATIC", "86400"))
    logger.info("CACHE_TTL_HTML=%s", os.getenv("CACHE_TTL_HTML", "300"))


def main() -> None:
    # Recreate settings so it reads current env vars
    settings = _Settings()

    errors = validate_settings(settings)
    if errors:
        for err in errors:
            logger.error(err)
        logger.error("Startup validation failed — exiting")
        sys.exit(2)

    print_diagnostics(settings)

    # Replace current process with uvicorn
    uvicorn_cmd = [
        "uvicorn",
        "replica.main:app",
        "--host",
        os.getenv("HOST", "0.0.0.0"),
        "--port",
        os.getenv("PORT", "8000"),
        "--proxy-headers",
    ]

    logger.info("Launching server: %s", " ".join(uvicorn_cmd))
    os.execvp("uvicorn", uvicorn_cmd)


if __name__ == "__main__":
    main()
