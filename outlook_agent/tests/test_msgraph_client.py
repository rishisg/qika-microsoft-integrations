"""
Unit tests for MicrosoftGraphClient (Outlook).
All network calls are mocked — no real API calls made.
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.outlook_agent.src.services.msgraph_client import MicrosoftGraphClient


@pytest.fixture
def graph_client(dummy_token_store):
    return MicrosoftGraphClient(
        token_store=dummy_token_store,
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="http://localhost:8010/outlook/oauth/callback",
        scopes=["https://graph.microsoft.com/Mail.Read"],
    )


@pytest.fixture
async def seeded_store(dummy_token_store):
    """Token store with a valid (non-expired) access token."""
    await dummy_token_store.set(
        tenant_id="tenant1",
        user_id="user1",
        data={
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_at": int(time.time()) + 3600,  # 1 hour from now
        },
    )
    return dummy_token_store


@pytest.mark.asyncio
async def test_get_valid_token_returns_access_token(seeded_store):
    client = MicrosoftGraphClient(
        token_store=seeded_store,
        client_id="cid",
        client_secret="csec",
        redirect_uri="http://localhost",
        scopes=[],
    )
    token = await client._get_valid_token("tenant1", "user1")
    assert token == "test-access-token"


@pytest.mark.asyncio
async def test_get_valid_token_raises_when_no_tokens(graph_client):
    with pytest.raises(ValueError, match="No tokens found"):
        await graph_client._get_valid_token("unknown_tenant", "unknown_user")


@pytest.mark.asyncio
async def test_list_messages_calls_graph(seeded_store, monkeypatch):
    """Verify list_messages sends correct GET request."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "value": [
            {"id": "msg1", "subject": "Hello", "isRead": False}
        ]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.is_closed = False

    client = MicrosoftGraphClient(
        token_store=seeded_store,
        client_id="cid",
        client_secret="csec",
        redirect_uri="http://localhost",
        scopes=[],
    )
    client._client = mock_client

    result = await client.list_messages(
        tenant_id="tenant1",
        user_id="user1",
        folder="inbox",
        max_results=10,
    )
    assert "value" in result
    assert result["value"][0]["subject"] == "Hello"
    mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_send_message_calls_send_mail(seeded_store):
    """Verify send_message posts to /me/sendMail."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.status_code = 202

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.is_closed = False

    client = MicrosoftGraphClient(
        token_store=seeded_store,
        client_id="cid",
        client_secret="csec",
        redirect_uri="http://localhost",
        scopes=[],
    )
    client._client = mock_client

    result = await client.send_message(
        tenant_id="tenant1",
        user_id="user1",
        to=["test@example.com"],
        subject="Test",
        body="Hello",
    )
    assert result["status"] == "sent"
    assert result["to"] == ["test@example.com"]
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert "/me/sendMail" in call_args[0][0]


@pytest.mark.asyncio
async def test_delete_message(seeded_store):
    """Verify delete_message calls DELETE on correct path."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.delete = AsyncMock(return_value=mock_response)
    mock_client.is_closed = False

    client = MicrosoftGraphClient(
        token_store=seeded_store,
        client_id="cid",
        client_secret="csec",
        redirect_uri="http://localhost",
        scopes=[],
    )
    client._client = mock_client

    await client.delete_message("tenant1", "user1", "msg123")
    mock_client.delete.assert_called_once()
    call_path = mock_client.delete.call_args[0][0]
    assert "msg123" in call_path
