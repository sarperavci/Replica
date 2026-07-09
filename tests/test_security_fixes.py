import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response as HTTPXResponse

from replica.main import app
from replica.config import settings

client = TestClient(app)
TARGET = settings.TARGET_ORIGIN.rstrip("/")


@respx.mock
def test_set_cookie_not_replayed_from_cache():
    """A Set-Cookie response must never be cached and replayed to other clients."""
    respx.get(f"{TARGET}/acct").respond(
        200,
        content="<html>hi</html>",
        headers={"content-type": "text/html", "set-cookie": "session=SECRET; Path=/"},
    )
    r1 = client.get("/acct")
    assert r1.headers.get("set-cookie") == "session=SECRET; Path=/"
    assert r1.headers.get("x-cache") == "MISS"

    r2 = client.get("/acct")
    # must re-fetch (MISS), not serve a cached copy carrying A's session cookie
    assert r2.headers.get("x-cache") == "MISS"


@respx.mock
def test_set_cookie_response_marked_private():
    respx.get(f"{TARGET}/acct2").respond(
        200,
        content="<html>hi</html>",
        headers={"content-type": "text/html", "set-cookie": "s=1"},
    )
    r = client.get("/acct2")
    assert "no-store" in r.headers.get("cache-control", "")


@respx.mock
def test_origin_no_store_not_cached():
    respx.get(f"{TARGET}/private").respond(
        200,
        content="<html>secret</html>",
        headers={"content-type": "text/html", "cache-control": "private, no-store"},
    )
    r1 = client.get("/private")
    assert r1.headers.get("x-cache") == "MISS"
    r2 = client.get("/private")
    assert r2.headers.get("x-cache") == "MISS"


@respx.mock
def test_multiple_set_cookie_preserved():
    def _handler(request):
        return HTTPXResponse(
            200,
            content="ok",
            headers=[
                ("content-type", "text/plain"),
                ("set-cookie", "a=1; Path=/"),
                ("set-cookie", "b=2; Path=/"),
            ],
        )

    respx.get(f"{TARGET}/multi").mock(side_effect=_handler)
    r = client.get("/multi")
    cookies = r.headers.get_list("set-cookie")
    values = "".join(cookies)
    assert "a=1" in values and "b=2" in values
    assert len(cookies) == 2


@respx.mock
def test_cloudflare_set_cookie_filtered():
    def _handler(request):
        return HTTPXResponse(
            200,
            content="ok",
            headers=[
                ("content-type", "text/plain"),
                ("set-cookie", "__cf_bm=xxx; Path=/"),
                ("set-cookie", "real=yes; Path=/"),
            ],
        )

    respx.get(f"{TARGET}/cf").mock(side_effect=_handler)
    r = client.get("/cf")
    values = "".join(r.headers.get_list("set-cookie"))
    assert "__cf_bm" not in values
    assert "real=yes" in values


@respx.mock
def test_inject_js_with_backslash_does_not_500(monkeypatch):
    """INJECT_JS containing regex/backslash content must not crash the request."""
    monkeypatch.setattr(settings, "INJECT_JS", r"var re=/\d+/; var s='\n';")
    respx.get(f"{TARGET}/bs").respond(
        200, content="<html><body>x</body></html>", headers={"content-type": "text/html"}
    )
    r = client.get("/bs")
    assert r.status_code == 200
    assert r"var re=/\d+/" in r.text


@respx.mock
def test_replacement_value_with_backslash_is_literal(monkeypatch):
    monkeypatch.setattr(settings, "REPLACEMENTS", {"PLACEHOLDER": r"a\1b"})
    respx.get(f"{TARGET}/repl").respond(
        200, content="<html>PLACEHOLDER</html>", headers={"content-type": "text/html"}
    )
    r = client.get("/repl")
    assert r.status_code == 200
    assert r"a\1b" in r.text


@respx.mock
def test_charset_relabeled_to_utf8():
    body = "café".encode("iso-8859-1")
    respx.get(f"{TARGET}/fr").respond(
        200, content=body, headers={"content-type": "text/html; charset=ISO-8859-1"}
    )
    r = client.get("/fr")
    assert "charset=utf-8" in r.headers.get("content-type", "").lower()
    assert "café".encode("utf-8") in r.content


@respx.mock
def test_hop_by_hop_request_headers_stripped():
    captured = {}

    def _handler(request):
        captured["headers"] = {k.lower() for k in request.headers.keys()}
        return HTTPXResponse(200, content="ok", headers={"content-type": "text/plain"})

    respx.get(f"{TARGET}/hop").mock(side_effect=_handler)
    # httpx re-adds its own Connection header, so assert on Upgrade/TE which it won't.
    client.get("/hop", headers={"Upgrade": "websocket", "TE": "trailers"})
    assert "upgrade" not in captured["headers"]
    assert "te" not in captured["headers"]


@respx.mock
def test_static_asset_cached():
    respx.get(f"{TARGET}/logo.png").respond(
        200, content=b"\x89PNG", headers={"content-type": "image/png"}
    )
    r1 = client.get("/logo.png")
    assert r1.headers.get("x-cache") == "MISS"
    r2 = client.get("/logo.png")
    assert r2.headers.get("x-cache") == "HIT"
