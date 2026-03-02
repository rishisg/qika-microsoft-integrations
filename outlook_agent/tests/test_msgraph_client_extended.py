"""
Additional tests for MicrosoftGraphClient covering:
reply, move, mark_as_read, list_mail_folders, get_me,
and token refresh when expired.
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.outlook_agent.src.services.msgraph_client import MicrosoftGraphClient


@pytest.fixture
async def seeded_store(dummy_token_store):
    await dummy_token_store.set(
        "t1", "u1",
        {"access_token": "tok", "refresh_token": "ref",
         "expires_at": int(time.time()) + 3600}
    )
    return dummy_token_store


def make_client(store):
    return MicrosoftGraphClient(
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
async def test_reply_message(seeded_store):
    m = AsyncMock()
    m.post = AsyncMock(return_value=mock_resp({}))
    m.is_closed = False
    c = make_client(seeded_store)
    c._client = m

    result = await c.reply_message("t1", "u1", "msg1", "Thanks!")
    assert result["status"] == "replied"
    assert "msg1" in m.post.call_args[0][0]


@pytest.mark.asyncio
async def test_move_message(seeded_store):
    m = AsyncMock()
    m.post = AsyncMock(return_value=mock_resp({"id": "msg1", "parentReference": {}}))
    m.is_closed = False
    c = make_client(seeded_store)
    c._client = m

    result = await c.move_message("t1", "u1", "msg1", "folder_dest")
    m.post.assert_called_once()
    assert "msg1" in m.post.call_args[0][0]


@pytest.mark.asyncio
async def test_mark_as_read_true(seeded_store):
    m = AsyncMock()
    m.patch = AsyncMock(return_value=mock_resp({}))
    m.is_closed = False
    c = make_client(seeded_store)
    c._client = m

    result = await c.mark_as_read("t1", "u1", "msg1", is_read=True)
    assert result["is_read"] is True
    assert result["message_id"] == "msg1"


@pytest.mark.asyncio
async def test_mark_as_unread(seeded_store):
    m = AsyncMock()
    m.patch = AsyncMock(return_value=mock_resp({}))
    m.is_closed = False
    c = make_client(seeded_store)
    c._client = m

    result = await c.mark_as_read("t1", "u1", "msg2", is_read=False)
    assert result["is_read"] is False


@pytest.mark.asyncio
async def test_list_mail_folders(seeded_store):
    folders = {"value": [
        {"id": "f1", "displayName": "Inbox", "totalItemCount": 10, "unreadItemCount": 2},
        {"id": "f2", "displayName": "Sent Items", "totalItemCount": 5, "unreadItemCount": 0},
    ]}
    m = AsyncMock()
    m.get = AsyncMock(return_value=mock_resp(folders))
    m.is_closed = False
    c = make_client(seeded_store)
    c._client = m

    result = await c.list_mail_folders("t1", "u1")
    assert len(result["value"]) == 2
    assert result["value"][0]["displayName"] == "Inbox"


@pytest.mark.asyncio
async def test_get_me(seeded_store):
    user = {"id": "u1", "displayName": "Test User", "mail": "test@hotmail.com"}
    m = AsyncMock()
    m.get = AsyncMock(return_value=mock_resp(user))
    m.is_closed = False
    c = make_client(seeded_store)
    c._client = m

    result = await c.get_me("t1", "u1")
    assert result["displayName"] == "Test User"


@pytest.mark.asyncio
async def test_get_message(seeded_store):
    msg = {"id": "msg1", "subject": "Hello", "body": {"content": "Hi there"}}
    m = AsyncMock()
    m.get = AsyncMock(return_value=mock_resp(msg))
    m.is_closed = False
    c = make_client(seeded_store)
    c._client = m

    result = await c.get_message("t1", "u1", "msg1")
    assert result["subject"] == "Hello"


@pytest.mark.asyncio
async def test_token_refresh_when_expired(dummy_token_store):
    """When token is expired, _refresh_token should be called."""
    await dummy_token_store.set("t1", "u1", {
        "access_token": "old_tok",
        "refresh_token": "ref_tok",
        "expires_at": int(time.time()) - 100,  # Already expired
    })

    refreshed = {
        "access_token": "new_tok",
        "refresh_token": "new_ref",
        "expires_in": 3600,
    }

    c = make_client(dummy_token_store)
    with patch.object(c, "_refresh_token", new=AsyncMock(return_value=refreshed)):
        token = await c._get_valid_token("t1", "u1")

    assert token == "new_tok"
    stored = await dummy_token_store.get("t1", "u1")
    assert stored["access_token"] == "new_tok"


@pytest.mark.asyncio
async def test_aclose(dummy_token_store):
    """aclose should not raise even with no client."""
    c = make_client(dummy_token_store)
    await c.aclose()  # _client is None, should be safe
