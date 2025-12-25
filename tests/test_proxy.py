import pytest
from fastapi.testclient import TestClient
from replica.main import app

client = TestClient(app)

import respx
from httpx import Response as HTTPXResponse
from replica.config import settings

TARGET = settings.TARGET_ORIGIN.rstrip('/')

@respx.mock
def test_proxy_get_request_mocked():
    route = respx.get(f"{TARGET}/some/path").respond(200, content="<html>Welcome to example.com</html>", headers={"content-type": "text/html"})

    resp = client.get("/some/path")
    assert resp.status_code == 200
    assert "Welcome to" in resp.text

@respx.mock
def test_proxy_replacement_and_cache_behavior(monkeypatch):
    monkeypatch.setattr(settings, "REPLACEMENTS", [{"from": "example.com", "to": "MY_HOST"}])
    route = respx.get(f"{TARGET}/cached").respond(200, content="<html>example.com content</html>", headers={"content-type": "text/html"})

    r1 = client.get("/cached")
    assert r1.status_code == 200
    assert "testserver content" in r1.text
    assert r1.headers.get("x-cache") == "MISS"

    route.return_value = HTTPXResponse(200, content="<html>changed</html>", headers={"content-type": "text/html"})

    r2 = client.get("/cached")
    assert r2.status_code == 200
    assert "testserver content" in r2.text
    assert r2.headers.get("x-cache") == "HIT"

@respx.mock
def test_proxy_header_sanitization_mocked():
    captured = {}
    def _handler(request):
        captured['headers'] = dict(request.headers)
        return HTTPXResponse(200, content="ok", headers={"content-type": "text/plain"})
    respx.get(f"{TARGET}/headers").mock(side_effect=_handler)

    r = client.get("/headers", headers={"X-Forwarded-For": "1.2.3.4", "User-Agent": "test-agent"})
    assert r.status_code == 200
    assert "X-Forwarded-For" not in captured['headers']
    assert captured['headers'].get('user-agent') == 'test-agent'


@respx.mock
def test_inject_js_when_set(monkeypatch):
    monkeypatch.setattr(settings, "INJECT_JS", "window.__injected = true;")
    route = respx.get(f"{TARGET}/inject").respond(200, content="<html><body>page</body></html>", headers={"content-type": "text/html"})

    r = client.get("/inject")
    assert r.status_code == 200
    assert "<script>window.__injected = true;</script>" in r.text


@respx.mock
def test_no_inject_when_unset(monkeypatch):
    monkeypatch.setattr(settings, "INJECT_JS", "")
    route = respx.get(f"{TARGET}/noinject").respond(200, content="<html><body>page</body></html>", headers={"content-type": "text/html"})

    r = client.get("/noinject")
    assert r.status_code == 200
    assert "<script>window.__injected = true;</script>" not in r.text
