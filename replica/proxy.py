from __future__ import annotations
from typing import Optional
from urllib.parse import urljoin
import re

from fastapi import Request, Response
import httpx
from httpx_curl_cffi import AsyncCurlTransport, CurlOpt


def _create_async_client(impersonate: str) -> httpx.AsyncClient:
    # Use curl options recommended for parallel requests
    curl_options = {CurlOpt.FRESH_CONNECT: True}
    transport = AsyncCurlTransport(impersonate=impersonate, default_headers=True, curl_options=curl_options)
    return httpx.AsyncClient(transport=transport, follow_redirects=True, timeout=30.0)

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

    # Derive request-scoped origin & host from incoming request so we do not
    # have to rely on a static environment variable. Prefer the Host header if
    # provided (since it may include an explicit port), otherwise fall back to
    # values present on request.url or settings.
    host_header = request.headers.get("host", "")
    if host_header:
        # split on last ':' to support IPv6 addresses like [::1]:8080
        host_part, sep, port_part = host_header.rpartition(":")
        if sep and port_part.isdigit():
            req_host = host_part or port_part  # if rpartition returned '' left-side
            req_port = port_part
        else:
            req_host = host_header
            req_port = None
    else:
        req_host = request.url.hostname or settings.my_host
        req_port = request.url.port

    scheme = request.url.scheme or "http"

    if req_port:
        incoming_origin = f"{scheme}://{req_host}:{req_port}"
    elif request.url.port:
        incoming_origin = f"{scheme}://{req_host}:{request.url.port}"
    else:
        incoming_origin = f"{scheme}://{req_host}"

    incoming_host = req_host

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
    
    # Filter out Cloudflare-specific cookies that should not be forwarded
    if "cookie" in request_headers:
        cookies = request_headers["cookie"].split("; ")
        filtered_cookies = [
            c for c in cookies 
            if not any(c.startswith(f"{name}=") for name in ["__cf_bm", "_cfuvid", "cf_clearance"])
        ]
        if filtered_cookies:
            request_headers["cookie"] = "; ".join(filtered_cookies)
        else:
            request_headers.pop("cookie", None)

    # Sanitize headers using the dynamically derived origin/host for this request
    # We provide an origin-like string for header sanitization (scheme://host[:port]).
    my_origin_for_headers = f"{scheme}://{incoming_host}"
    request_headers = sanitize_request_headers(request_headers, my_origin_for_headers, incoming_host, settings.TARGET_ORIGIN)

    body: Optional[bytes] = None
    if method not in ("GET", "HEAD"):
        body = await request.body()

    # Choose impersonation profile based on incoming User-Agent
    ua = request.headers.get("user-agent", "")
    impersonate = "firefox" if "firefox" in ua.lower() else "chrome"

    try:
        async with _create_async_client(impersonate) as client:
            upstream = await client.request(method=method, url=target_url, headers=request_headers, content=body)
    except Exception as exc:  # pragma: no cover - network error
        return Response(content=f"Upstream fetch error: {exc}", status_code=502)

    # Sanitize response headers using the dynamically derived origin/host for this request
    resp_headers = sanitize_response_headers(dict(upstream.headers), settings.TARGET_ORIGIN, settings.target_host, my_origin_for_headers, incoming_host)
    content_type = resp_headers.get("content-type", "")

    is_text = any(t in content_type.lower() for t in ("text", "json", "javascript", "xml", "html"))

    if is_static_file(target_path, settings.STATIC_EXTENSIONS) or not is_text:
        # static / binary -> cache server-side
        del resp_headers["cache-control"] #= "no-cache, no-store, must-revalidate"
        del resp_headers["pragma"] #= "no-cache"
        del resp_headers["expires"] #= "0"
        resp_headers["x-cache"] = "MISS"
        body_bytes = upstream.content

        if 200 <= upstream.status_code < 300 and method == "GET":
            _static_cache.put(cache_key, (body_bytes, resp_headers, upstream.status_code), settings.CACHE_TTL_STATIC)

        return Response(content=body_bytes, status_code=upstream.status_code, headers=resp_headers)

    try:
        text = upstream.text
    except Exception:
        text = upstream.content.decode("utf-8", errors="replace")

    # Ensure target origin/host -> incoming origin/host replacement is always applied and overrides
    # any user-specified replacement for the target. We filter out user-supplied replacements that
    # reference the configured target to avoid them overriding the mandatory mapping, then append
    # the mandatory mappings so they are applied last.
    user_replacements = getattr(settings, "REPLACEMENTS", {}) or {}
    filtered_replacements = {}
    
    # Filter out user replacements that target the configured target host/origin
    for from_str, to_str in user_replacements.items():
        # If the user tries to target the configured target host/origin, ignore it so we enforce
        # replacement unconditionally.
        if settings.target_host.lower() in from_str.lower() or settings.TARGET_ORIGIN.lower() in from_str.lower():
            continue
        filtered_replacements[from_str] = to_str

    # Add mandatory mappings: replace full origin first, then fallback to host-only for cases
    # where the content references just the hostname without scheme.
    filtered_replacements[settings.TARGET_ORIGIN.rstrip("/")] = incoming_origin.rstrip("/")
    filtered_replacements[settings.target_host] = f"{incoming_host}:{req_port}" if req_port else incoming_host

    # Perform replacements using the filtered dict.
    text = perform_text_replacements(text, filtered_replacements, incoming_host)

    if "html" in content_type.lower():
        # Optionally inject inline JS into <head> or <body> based on INJECT_JS_LOCATION.
        if getattr(settings, "INJECT_JS", ""):
            js_snippet = f"<script>{settings.INJECT_JS}</script>"
            inject_location = getattr(settings, "INJECT_JS_LOCATION", "body").lower()

            if inject_location == "head":
                # Inject before closing </head> tag
                if re.search(r"</head>", text, flags=re.IGNORECASE):
                    text = re.sub(r"</head>", js_snippet + "</head>", text, flags=re.IGNORECASE)
                elif re.search(r"<head[^>]*>", text, flags=re.IGNORECASE):
                    # If no closing </head> but opening <head> exists, insert after it
                    text = re.sub(r"(<head[^>]*>)", r"\1" + js_snippet, text, flags=re.IGNORECASE)
                else:
                    # Fallback: prepend to content
                    text = js_snippet + text
            else:
                # Default: inject before closing </body> tag
                if re.search(r"</body>", text, flags=re.IGNORECASE):
                    text = re.sub(r"</body>", js_snippet + "</body>", text, flags=re.IGNORECASE)
                else:
                    text = text + js_snippet

        del resp_headers["cache-control"] #= "no-cache, no-store, must-revalidate"
        del resp_headers["pragma"] #= "no-cache"
        del resp_headers["expires"] #= "0"
        resp_headers["x-cache"] = "MISS"
        body_bytes = text.encode("utf-8")
        if 200 <= upstream.status_code < 300 and method == "GET":
            _html_cache.put(cache_key, (body_bytes, resp_headers, upstream.status_code), settings.CACHE_TTL_HTML)
        return Response(content=body_bytes, status_code=upstream.status_code, headers=resp_headers)

    body_bytes = text.encode("utf-8")
    return Response(content=body_bytes, status_code=upstream.status_code, headers=resp_headers)
