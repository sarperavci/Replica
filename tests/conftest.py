import os
import sys
import pytest
from httpx import AsyncClient

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from replica.main import app

# Ensure tests use the real httpx AsyncClient for upstream requests (so respx can
# mock responses reliably) by monkeypatching the module-level factory to return
# a standard AsyncClient. This fixture runs automatically for all tests.
import pytest
import httpx
import replica.proxy as proxy_module

@pytest.fixture(autouse=True)
def use_real_httpx_transport(monkeypatch):
    def _factory(impersonate: str):
        return httpx.AsyncClient(follow_redirects=True, timeout=30.0)
    monkeypatch.setattr(proxy_module, "_create_async_client", _factory)
    yield

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def sample_data():
    return {
        "key": "value",
        "another_key": "another_value"
    }