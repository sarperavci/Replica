from __future__ import annotations
from typing import Optional
from urllib.parse import urljoin
import re

from fastapi import Request, Response
import httpx

from .config import settings
from .cache import Cache
from .utils import (
    is_static_file,
    perform_text_replacements,
    sanitize_request_headers,
    sanitize_response_headers,
)

# module-level caches
_static_cache = Cache()
_html_cache = Cache()


async def proxy_request(request: Request, path: str) -> Response:
    """Handle incoming request and proxy to the configured target origin.

    This function mirrors typical reverse-proxy behavior with header sanitization,
    optional content replacements and in-memory TTL caching for static and HTML content.
    """
    method = request.method

    qs = str(request.url.query)
    target_path = request.url.path
    target_url = urljoin(settings.TARGET_ORIGIN, target_path)
    if qs:
        target_url = f"{target_url}?{qs}"

    incoming_url = str(request.url)
    incoming_host = request.url.hostname or settings.my_host

    cache_key = f"{method}:{incoming_url}"

    if method == "GET":
        cache_store = _static_cache if is_static_file(target_path, settings.STATIC_EXTENSIONS) else _html_cache
        cached = cache_store.get(cache_key)
        if cached:
            data, headers, status = cached
            headers = dict(headers)
            headers["x-cache"] = "HIT"
            return Response(content=data, status_code=status, headers=headers)

    request_headers = dict(request.headers)
    request_headers["host"] = settings.target_host
    request_headers.pop("accept-encoding", None)

    request_headers = sanitize_request_headers(request_headers, settings.MY_ORIGIN, settings.my_host, settings.TARGET_ORIGIN)

    body: Optional[bytes] = None
    if method not in ("GET", "HEAD"):
        body = await request.body()

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            upstream = await client.request(method=method, url=target_url, headers=request_headers, content=body)
    except Exception as exc:  # pragma: no cover - network error
        return Response(content=f"Upstream fetch error: {exc}", status_code=502)

    resp_headers = sanitize_response_headers(dict(upstream.headers), settings.TARGET_ORIGIN, settings.target_host, settings.MY_ORIGIN, settings.my_host)
    content_type = resp_headers.get("content-type", "")

    is_text = any(t in content_type.lower() for t in ("text", "json", "javascript", "xml", "html"))

    if is_static_file(target_path, settings.STATIC_EXTENSIONS) or not is_text:
        # static / binary -> cache aggressively
        resp_headers["cache-control"] = f"public, max-age={settings.CACHE_TTL_STATIC}"
        resp_headers["x-cache"] = "MISS"
        body_bytes = upstream.content

        if 200 <= upstream.status_code < 300 and method == "GET":
            _static_cache.put(cache_key, (body_bytes, resp_headers, upstream.status_code), settings.CACHE_TTL_STATIC)

        return Response(content=body_bytes, status_code=upstream.status_code, headers=resp_headers)

    try:
        text = upstream.text
    except Exception:
        text = upstream.content.decode("utf-8", errors="replace")

    text = perform_text_replacements(text, settings.REPLACEMENTS, incoming_host)

    if "html" in content_type.lower():
        # Optionally inject inline JS before the closing </body> tag.
        if getattr(settings, "INJECT_JS", ""):
            js_snippet = f"<script>{settings.INJECT_JS}</script>"
            if re.search(r"</body>", text, flags=re.IGNORECASE):
                text = re.sub(r"</body>", js_snippet + "</body>", text, flags=re.IGNORECASE)
            else:
                text = text + js_snippet

        resp_headers["cache-control"] = f"public, max-age={settings.CACHE_TTL_HTML}"
        resp_headers["x-cache"] = "MISS"
        body_bytes = text.encode("utf-8")
        if 200 <= upstream.status_code < 300 and method == "GET":
            _html_cache.put(cache_key, (body_bytes, resp_headers, upstream.status_code), settings.CACHE_TTL_HTML)
        return Response(content=body_bytes, status_code=upstream.status_code, headers=resp_headers)

    body_bytes = text.encode("utf-8")
    return Response(content=body_bytes, status_code=upstream.status_code, headers=resp_headers)
