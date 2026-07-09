import os
import sys

import pytest
import httpx
from httpx import ASGITransport, AsyncClient

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from replica.main import app
import replica.proxy as proxy_module


@pytest.fixture(autouse=True)
def use_real_httpx_transport(monkeypatch):
    """Swap the curl transport for a plain AsyncClient so respx can mock upstream,
    and reset shared proxy state so tests don't leak into each other."""
    def _factory(impersonate: str):
        return httpx.AsyncClient(follow_redirects=True, timeout=30.0)

    monkeypatch.setattr(proxy_module, "_create_async_client", _factory)
    proxy_module._static_cache.clear()
    proxy_module._html_cache.clear()
    proxy_module._clients.clear()
    yield
    proxy_module._static_cache.clear()
    proxy_module._html_cache.clear()
    proxy_module._clients.clear()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def sample_data():
    return {"key": "value", "another_key": "another_value"}
