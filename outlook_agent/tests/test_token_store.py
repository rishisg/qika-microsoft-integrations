"""
Comprehensive tests for Outlook token_store.py
Covers: FileTokenStore.get, set, delete, link_user_tokens, encode_state, decode_state
"""
import json
import pytest
from pathlib import Path

from agents.outlook_agent.src.services.token_store import (
    FileTokenStore, encode_state, decode_state
)


@pytest.fixture
def store(tmp_path):
    return FileTokenStore(path=str(tmp_path / "tokens" / "token.json"))


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(store):
    result = await store.get("tenant1", "user1")
    assert result is None


@pytest.mark.asyncio
async def test_set_and_get(store):
    data = {"access_token": "tok123", "expires_at": 9999}
    await store.set("tenant1", "user1", data)
    result = await store.get("tenant1", "user1")
    assert result == data


@pytest.mark.asyncio
async def test_set_uses_default_when_user_id_none(store):
    data = {"access_token": "tok_default"}
    await store.set("tenant1", None, data)
    result = await store.get("tenant1", None)
    assert result == data


@pytest.mark.asyncio
async def test_delete_removes_token(store):
    await store.set("tenant1", "user1", {"access_token": "tok"})
    await store.delete("tenant1", "user1")
    result = await store.get("tenant1", "user1")
    assert result is None


@pytest.mark.asyncio
async def test_delete_nonexistent_is_safe(store):
    # Should not raise
    await store.delete("tenant1", "ghost_user")


@pytest.mark.asyncio
async def test_link_user_tokens_success(store):
    data = {"access_token": "tok_source"}
    await store.set("tenant1", "user_a", data)
    await store.link_user_tokens("tenant1", "user_a", "user_b")
    result = await store.get("tenant1", "user_b")
    assert result == data


@pytest.mark.asyncio
async def test_link_user_tokens_raises_when_source_missing(store):
    with pytest.raises(ValueError, match="No tokens found"):
        await store.link_user_tokens("tenant1", "ghost", "user_b")


@pytest.mark.asyncio
async def test_multiple_tenants_isolated(store):
    await store.set("tenant_a", "user1", {"tok": "A"})
    await store.set("tenant_b", "user1", {"tok": "B"})
    assert (await store.get("tenant_a", "user1"))["tok"] == "A"
    assert (await store.get("tenant_b", "user1"))["tok"] == "B"


def test_encode_state_roundtrip():
    data = {"tenant_id": "t1", "user_id": "u1", "extra": "val"}
    encoded = encode_state(data)
    decoded = decode_state(encoded)
    assert decoded == data


def test_decode_state_invalid_returns_empty():
    result = decode_state("not-valid-base64!!!")
    assert result == {}


def test_encode_state_is_string():
    encoded = encode_state({"k": "v"})
    assert isinstance(encoded, str)
    assert len(encoded) > 0
