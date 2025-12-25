import pytest

import replica.proxy as proxy_module


class DummyTransport:
    def __init__(self, *args, **kwargs):
        # Record what was passed to the transport so tests can assert behavior
        DummyTransport.last = {"args": args, "kwargs": kwargs}
        # Keep some attributes for compatibility checks
        self.impersonate = kwargs.get("impersonate")
        self.default_headers = kwargs.get("default_headers", False)
        self.curl_options = kwargs.get("curl_options")


class DummyClient:
    def __init__(self, transport=None, follow_redirects=False, timeout=None):
        self.transport = transport
        self.follow_redirects = follow_redirects
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_create_client_uses_curl_transport_when_available(monkeypatch):
    # Temporarily replace AsyncCurlTransport with our dummy to verify it gets called
    # with the correct impersonation parameter. Since the import happens at module
    # load time, we need to reload the module after monkeypatching.
    import importlib
    
    monkeypatch.setattr("httpx_curl_cffi.AsyncCurlTransport", DummyTransport)
    monkeypatch.setattr("httpx_curl_cffi.CurlOpt", type("O", (), {"FRESH_CONNECT": "fresh"}))
    
    # Reload to pick up monkeypatched imports
    importlib.reload(proxy_module)

    client = proxy_module._create_async_client("firefox")

    # Ensure our DummyTransport constructor was called with the impersonation profile
    assert getattr(DummyTransport, "last", None) is not None
    assert DummyTransport.last["kwargs"]["impersonate"] == "firefox"
