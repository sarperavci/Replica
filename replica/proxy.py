from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import re

from fastapi import Request, Response
import httpx
from httpx_curl_cffi import AsyncCurlTransport, CurlOpt

from .config import settings
from .cache import Cache
from .utils import (
    is_cloudflare_cookie,
    is_static_file,
    perform_text_replacements,
    rewrite_set_cookie,
    sanitize_request_headers,
    sanitize_response_headers,
)

# Hop-by-hop headers must not be forwarded to the upstream (RFC 7230 §6.1).
# content-length/transfer-encoding are recomputed by httpx from the body we pass.
HOP_BY_HOP = frozenset({
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-length",
})


def _create_async_client(impersonate: str) -> httpx.AsyncClient:
    transport = AsyncCurlTransport(impersonate=impersonate, default_headers=True)
    return httpx.AsyncClient(transport=transport, follow_redirects=True, timeout=30.0)


# Persistent per-profile clients, created at startup so connections are pooled
# and reused across requests instead of rebuilt per request.
_clients: Dict[str, httpx.AsyncClient] = {}


async def startup_clients() -> None:
    for profile in ("chrome", "firefox"):
        _clients[profile] = _create_async_client(profile)


async def shutdown_clients() -> None:
    for client in _clients.values():
        try:
            await client.aclose()
        except Exception:  # pragma: no cover - best-effort cleanup
            pass
    _clients.clear()


def _get_client(impersonate: str) -> Tuple[httpx.AsyncClient, bool]:
    """Return (client, ephemeral). Reuse the pooled client when available."""
    client = _clients.get(impersonate)
    if client is not None:
        return client, False
    return _create_async_client(impersonate), True


# module-level caches
_static_cache = Cache()
_html_cache = Cache()


def _relabel_utf8(content_type: str) -> str:
    if not content_type:
        return "text/html; charset=utf-8"
    if "charset=" in content_type.lower():
        return re.sub(r"charset=[^;]+", "charset=utf-8", content_type, flags=re.IGNORECASE)
    return f"{content_type}; charset=utf-8"


def _origin_forbids_caching(cache_control: str) -> bool:
    cc = cache_control.lower()
    return any(token in cc for token in ("no-store", "no-cache", "private"))


def _extract_set_cookies(upstream: httpx.Response, target_origin: str, target_host: str,
                         my_origin: str, my_host: str) -> List[str]:
    """Preserve each Set-Cookie header separately, drop Cloudflare cookies, rewrite host/domain."""
    cookies: List[str] = []
    for name, value in upstream.headers.multi_items():
        if name.lower() != "set-cookie":
            continue
        if is_cloudflare_cookie(value):
            continue
        cookies.append(rewrite_set_cookie(value, target_origin, target_host, my_origin, my_host))
    return cookies


def _apply_cache_headers(resp_headers: Dict[str, str], cacheable: bool, ttl: int) -> None:
    resp_headers.pop("pragma", None)
    resp_headers.pop("expires", None)
    if cacheable:
        resp_headers["cache-control"] = f"public, max-age={ttl}"
    else:
        resp_headers["cache-control"] = "private, no-store"


async def proxy_request(request: Request, path: str) -> Response:
    """Handle incoming request and proxy to the configured target origin.

    Mirrors typical reverse-proxy behavior with header sanitization, optional
    content replacements and in-memory TTL caching for static and HTML content.
    """
    method = request.method

    qs = str(request.url.query)
    target_path = request.url.path
    # Preserve any base path in TARGET_ORIGIN (urljoin would drop it for absolute paths).
    target_url = settings.TARGET_ORIGIN.rstrip("/") + "/" + target_path.lstrip("/")
    if qs:
        target_url = f"{target_url}?{qs}"

    incoming_url = str(request.url)

    # Derive request-scoped origin & host from the incoming request. Prefer the Host
    # header if provided (it may carry an explicit port), else fall back to request.url.
    host_header = request.headers.get("host", "")
    if host_header:
        host_part, sep, port_part = host_header.rpartition(":")
        if sep and port_part.isdigit():
            req_host = host_part or port_part
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

    is_static = is_static_file(target_path, settings.STATIC_EXTENSIONS)

    if method == "GET":
        cache_store = _static_cache if is_static else _html_cache
        cached = cache_store.get(cache_key)
        if cached:
            data, headers, status = cached
            headers = dict(headers)
            headers["x-cache"] = "HIT"
            return Response(content=data, status_code=status, headers=headers)

    request_headers = dict(request.headers)
    request_headers["host"] = settings.target_host
    request_headers.pop("accept-encoding", None)
    for h in list(request_headers):
        if h.lower() in HOP_BY_HOP:
            request_headers.pop(h, None)

    # Filter out Cloudflare-specific request cookies that should not be forwarded.
    if "cookie" in request_headers:
        cookies = request_headers["cookie"].split("; ")
        filtered_cookies = [c for c in cookies if not is_cloudflare_cookie(c)]
        if filtered_cookies:
            request_headers["cookie"] = "; ".join(filtered_cookies)
        else:
            request_headers.pop("cookie", None)

    my_origin_for_headers = f"{scheme}://{incoming_host}"
    request_headers = sanitize_request_headers(request_headers, my_origin_for_headers, incoming_host, settings.TARGET_ORIGIN)

    body: Optional[bytes] = None
    if method not in ("GET", "HEAD"):
        body = await request.body()

    ua = request.headers.get("user-agent", "")
    impersonate = "firefox" if "firefox" in ua.lower() else "chrome"

    client, ephemeral = _get_client(impersonate)
    try:
        if ephemeral:
            async with client:
                upstream = await client.request(method=method, url=target_url, headers=request_headers, content=body)
        else:
            upstream = await client.request(method=method, url=target_url, headers=request_headers, content=body)
    except Exception as exc:  # pragma: no cover - network error
        return Response(content=f"Upstream fetch error: {exc}", status_code=502)

    resp_headers = sanitize_response_headers(dict(upstream.headers), settings.TARGET_ORIGIN, settings.target_host, my_origin_for_headers, incoming_host)
    resp_headers.pop("set-cookie", None)  # handled separately to preserve multiple cookies

    set_cookies = _extract_set_cookies(upstream, settings.TARGET_ORIGIN, settings.target_host, my_origin_for_headers, incoming_host)

    content_type = resp_headers.get("content-type", "")
    is_text = any(t in content_type.lower() for t in ("text", "json", "javascript", "xml", "html"))

    is_success = 200 <= upstream.status_code < 300
    origin_no_cache = _origin_forbids_caching(upstream.headers.get("cache-control", ""))
    cacheable = method == "GET" and is_success and not set_cookies and not origin_no_cache

    def _finish(body_bytes: bytes, ttl: int, store: Optional[Cache]) -> Response:
        _apply_cache_headers(resp_headers, cacheable, ttl)
        resp_headers["x-cache"] = "MISS"
        if cacheable and store is not None:
            # Never persist Set-Cookie into the shared cache.
            store.put(cache_key, (body_bytes, dict(resp_headers), upstream.status_code), ttl)
        response = Response(content=body_bytes, status_code=upstream.status_code, headers=resp_headers)
        for cookie in set_cookies:
            response.headers.append("set-cookie", cookie)
        return response

    if is_static or not is_text:
        return _finish(upstream.content, settings.CACHE_TTL_STATIC, _static_cache)

    try:
        text = upstream.text
    except Exception:
        text = upstream.content.decode("utf-8", errors="replace")

    # The mandatory target -> incoming mapping always wins over user replacements.
    user_replacements = getattr(settings, "REPLACEMENTS", {}) or {}
    filtered_replacements: Dict[str, str] = {}
    for from_str, to_str in user_replacements.items():
        if settings.target_host.lower() in from_str.lower() or settings.TARGET_ORIGIN.lower() in from_str.lower():
            continue
        filtered_replacements[from_str] = to_str

    filtered_replacements[settings.TARGET_ORIGIN.rstrip("/")] = incoming_origin.rstrip("/")
    filtered_replacements[settings.target_host] = f"{incoming_host}:{req_port}" if req_port else incoming_host

    text = perform_text_replacements(text, filtered_replacements, incoming_host)

    if "html" in content_type.lower():
        if getattr(settings, "INJECT_JS", ""):
            js_snippet = f"<script>{settings.INJECT_JS}</script>"
            inject_location = getattr(settings, "INJECT_JS_LOCATION", "body").lower()
            repl_head = lambda m: js_snippet + m.group(0)
            if inject_location == "head":
                if re.search(r"</head>", text, flags=re.IGNORECASE):
                    text = re.sub(r"</head>", repl_head, text, flags=re.IGNORECASE)
                elif re.search(r"<head[^>]*>", text, flags=re.IGNORECASE):
                    text = re.sub(r"<head[^>]*>", lambda m: m.group(0) + js_snippet, text, flags=re.IGNORECASE)
                else:
                    text = js_snippet + text
            else:
                if re.search(r"</body>", text, flags=re.IGNORECASE):
                    text = re.sub(r"</body>", repl_head, text, flags=re.IGNORECASE)
                else:
                    text = text + js_snippet

        resp_headers["content-type"] = _relabel_utf8(content_type)
        return _finish(text.encode("utf-8"), settings.CACHE_TTL_HTML, _html_cache)

    resp_headers["content-type"] = _relabel_utf8(content_type)
    return _finish(text.encode("utf-8"), settings.CACHE_TTL_HTML, None)
