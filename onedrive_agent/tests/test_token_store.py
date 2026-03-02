"""
Tests for OneDrive token_store (mirrors Outlook token_store tests).
"""
import pytest
from agents.onedrive_agent.src.services.token_store import (
    FileTokenStore, encode_state, decode_state
)


@pytest.fixture
def store(tmp_path):
    return FileTokenStore(path=str(tmp_path / "tokens" / "token.json"))


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(store):
    assert await store.get("t1", "u1") is None


@pytest.mark.asyncio
async def test_set_and_get(store):
    data = {"access_token": "tok", "expires_at": 9999}
    await store.set("t1", "u1", data)
    assert await store.get("t1", "u1") == data


@pytest.mark.asyncio
async def test_default_user_id(store):
    data = {"access_token": "default_tok"}
    await store.set("t1", None, data)
    assert await store.get("t1", None) == data


@pytest.mark.asyncio
async def test_delete(store):
    await store.set("t1", "u1", {"tok": "x"})
    await store.delete("t1", "u1")
    assert await store.get("t1", "u1") is None


@pytest.mark.asyncio
async def test_delete_nonexistent_safe(store):
    await store.delete("t1", "ghost")  # Should not raise


@pytest.mark.asyncio
async def test_link_user_tokens(store):
    await store.set("t1", "src", {"access_token": "src_tok"})
    await store.link_user_tokens("t1", "src", "dst")
    assert (await store.get("t1", "dst"))["access_token"] == "src_tok"


@pytest.mark.asyncio
async def test_link_user_tokens_missing_source_raises(store):
    with pytest.raises(ValueError, match="No tokens found"):
        await store.link_user_tokens("t1", "ghost", "dst")


@pytest.mark.asyncio
async def test_multiple_tenants(store):
    await store.set("t1", "u1", {"tok": "A"})
    await store.set("t2", "u1", {"tok": "B"})
    assert (await store.get("t1", "u1"))["tok"] == "A"
    assert (await store.get("t2", "u1"))["tok"] == "B"


def test_encode_decode_roundtrip():
    data = {"tenant_id": "t1", "user_id": "u1"}
    assert decode_state(encode_state(data)) == data


def test_decode_invalid_state():
    assert decode_state("invalid!!!") == {}
