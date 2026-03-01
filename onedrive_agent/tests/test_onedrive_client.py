"""Unit tests for OneDriveGraphClient."""
import base64
import time
import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.onedrive_agent.src.services.onedrive_client import OneDriveGraphClient


@pytest.fixture
def client(dummy_token_store):
    return OneDriveGraphClient(
        token_store=dummy_token_store,
        client_id="test-client",
        client_secret="test-secret",
        redirect_uri="http://localhost:8011/onedrive/oauth/callback",
        scopes=["https://graph.microsoft.com/Files.ReadWrite.All"],
    )


@pytest.fixture
async def seeded_store(dummy_token_store):
    await dummy_token_store.set(
        "tenant1", "user1",
        {"access_token": "tok", "refresh_token": "ref", "expires_at": int(time.time()) + 3600},
    )
    return dummy_token_store


@pytest.mark.asyncio
async def test_get_valid_token_returns_token(seeded_store):
    c = OneDriveGraphClient(
        token_store=seeded_store, client_id="cid", client_secret="cs",
        redirect_uri="http://localhost", scopes=[],
    )
    token = await c._get_valid_token("tenant1", "user1")
    assert token == "tok"


@pytest.mark.asyncio
async def test_get_valid_token_raises_no_tokens(client):
    with pytest.raises(ValueError, match="No tokens found"):
        await client._get_valid_token("ghost", "ghost")


@pytest.mark.asyncio
async def test_list_items_root(seeded_store):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"value": [
        {"id": "f1", "name": "Documents", "folder": {}, "size": 0},
        {"id": "f2", "name": "photo.jpg", "file": {}, "size": 1024},
    ]}
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.is_closed = False

    c = OneDriveGraphClient(
        token_store=seeded_store, client_id="cid", client_secret="cs",
        redirect_uri="http://localhost", scopes=[],
    )
    c._client = mock_client

    result = await c.list_items("tenant1", "user1")
    assert len(result["value"]) == 2
    assert result["value"][0]["name"] == "Documents"


@pytest.mark.asyncio
async def test_upload_file(seeded_store):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"id": "item1", "name": "hello.txt", "size": 5, "webUrl": "https://..."}
    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_resp)
    mock_client.is_closed = False

    c = OneDriveGraphClient(
        token_store=seeded_store, client_id="cid", client_secret="cs",
        redirect_uri="http://localhost", scopes=[],
    )
    c._client = mock_client

    result = await c.upload_file("tenant1", "user1", "hello.txt", b"hello", mime_type="text/plain")
    assert result["name"] == "hello.txt"
    mock_client.put.assert_called_once()
    assert "hello.txt" in mock_client.put.call_args[0][0]


@pytest.mark.asyncio
async def test_delete_item(seeded_store):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.delete = AsyncMock(return_value=mock_resp)
    mock_client.is_closed = False

    c = OneDriveGraphClient(
        token_store=seeded_store, client_id="cid", client_secret="cs",
        redirect_uri="http://localhost", scopes=[],
    )
    c._client = mock_client

    await c.delete_item("tenant1", "user1", "item1")
    mock_client.delete.assert_called_once()
    assert "item1" in mock_client.delete.call_args[0][0]


@pytest.mark.asyncio
async def test_create_folder(seeded_store):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"id": "folder1", "name": "Reports", "webUrl": "https://..."}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.is_closed = False

    c = OneDriveGraphClient(
        token_store=seeded_store, client_id="cid", client_secret="cs",
        redirect_uri="http://localhost", scopes=[],
    )
    c._client = mock_client

    result = await c.create_folder("tenant1", "user1", "Reports")
    assert result["name"] == "Reports"
    call_json = mock_client.post.call_args[1]["json"]
    assert call_json["name"] == "Reports"
