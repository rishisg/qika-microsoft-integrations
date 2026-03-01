import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))


class DummyTokenStore:
    def __init__(self):
        self.data = {}

    async def get(self, tenant_id: str, user_id=None):
        return self.data.get(tenant_id, {}).get(user_id or "default")

    async def set(self, tenant_id: str, user_id, data):
        self.data.setdefault(tenant_id, {})[user_id or "default"] = data

    async def delete(self, tenant_id: str, user_id=None):
        self.data.get(tenant_id, {}).pop(user_id or "default", None)

    async def link_user_tokens(self, tenant_id, source_user_id, target_user_id):
        tokens = await self.get(tenant_id, source_user_id)
        if tokens is None:
            raise ValueError(f"No tokens for {source_user_id}")
        await self.set(tenant_id, target_user_id, tokens)


@pytest.fixture
def dummy_token_store():
    return DummyTokenStore()


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Prevent real network calls in unit tests."""
    class _NoNetwork:
        def __init__(self, *a, **kw):
            pass
        async def request(self, *a, **kw):
            raise RuntimeError("Network calls are blocked in tests")
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr("httpx.AsyncClient", _NoNetwork)
    monkeypatch.setattr("httpx.Client", _NoNetwork)
