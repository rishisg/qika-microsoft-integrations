"""Additional OneDrive Graph client tests: share, download, get_metadata, token refresh, drive_info."""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.onedrive_agent.src.services.onedrive_client import OneDriveGraphClient


@pytest.fixture
async def seeded_store(dummy_token_store):
    await dummy_token_store.set(
        "t1", "u1",
        {"access_token": "tok", "refresh_token": "ref",
         "expires_at": int(time.time()) + 3600}
    )
    return dummy_token_store


def make_client(store):
    return OneDriveGraphClient(
        token_store=store, client_id="cid", client_secret="cs",
        redirect_uri="http://localhost", scopes=[],
    )


def mock_resp(json_data=None, status=200):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data or {}
    return resp


@pytest.mark.asyncio
async def test_get_drive_info(seeded_store):
    m = AsyncMock()
    m.get = AsyncMock(return_value=mock_resp({"id": "d1", "driveType": "personal", "quota": {}}))
    m.is_closed = False
    c = make_client(seeded_store)
    c._client = m

    result = await c.get_drive_info("t1", "u1")
    assert result["driveType"] == "personal"


@pytest.mark.asyncio
async def test_share_item(seeded_store):
    m = AsyncMock()
    m.post = AsyncMock(return_value=mock_resp({"value": []}))
    m.is_closed = False
    c = make_client(seeded_store)
    c._client = m

    result = await c.share_item("t1", "u1", "item1", ["b@c.com"], role="read")
    m.post.assert_called_once()
    assert "item1" in m.post.call_args[0][0]
    call_json = m.post.call_args[1]["json"]
    assert call_json["roles"] == ["read"]
    assert call_json["recipients"][0]["email"] == "b@c.com"


@pytest.mark.asyncio
async def test_get_item_metadata(seeded_store):
    m = AsyncMock()
    m.get = AsyncMock(return_value=mock_resp({"id": "item1", "name": "test.txt", "size": 100}))
    m.is_closed = False
    c = make_client(seeded_store)
    c._client = m

    result = await c.get_item_metadata("t1", "u1", "item1")
    assert result["name"] == "test.txt"
    assert "item1" in m.get.call_args[0][0]


@pytest.mark.asyncio
async def test_create_folder_with_parent(seeded_store):
    m = AsyncMock()
    m.post = AsyncMock(return_value=mock_resp({"id": "fld1", "name": "Reports"}))
    m.is_closed = False
    c = make_client(seeded_store)
    c._client = m

    result = await c.create_folder("t1", "u1", "Reports", parent_path="Documents")
    assert "Documents" in m.post.call_args[0][0]
    assert result["name"] == "Reports"


@pytest.mark.asyncio
async def test_upload_with_folder_path(seeded_store):
    m = AsyncMock()
    m.put = AsyncMock(return_value=mock_resp({"id": "i1", "name": "file.txt", "size": 5}))
    m.is_closed = False
    c = make_client(seeded_store)
    c._client = m

    result = await c.upload_file("t1", "u1", "file.txt", b"hello",
                                  folder_path="Documents", mime_type="text/plain")
    assert "Documents/file.txt" in m.put.call_args[0][0]


@pytest.mark.asyncio
async def test_token_refresh_when_expired(dummy_token_store):
    await dummy_token_store.set("t1", "u1", {
        "access_token": "old", "refresh_token": "ref",
        "expires_at": int(time.time()) - 60,
    })
    refreshed = {"access_token": "new_tok", "refresh_token": "new_ref", "expires_in": 3600}
    c = make_client(dummy_token_store)
    with patch.object(c, "_refresh_token", new=AsyncMock(return_value=refreshed)):
        token = await c._get_valid_token("t1", "u1")
    assert token == "new_tok"


@pytest.mark.asyncio
async def test_aclose_safe_when_no_client(dummy_token_store):
    c = make_client(dummy_token_store)
    await c.aclose()  # Should not raise


@pytest.mark.asyncio
async def test_list_items_with_folder_path(seeded_store):
    m = AsyncMock()
    m.get = AsyncMock(return_value=mock_resp({"value": []}))
    m.is_closed = False
    c = make_client(seeded_store)
    c._client = m

    await c.list_items("t1", "u1", folder_path="Reports/Q1")
    # URL should contain the folder path
    assert "Reports/Q1" in m.get.call_args[0][0]
