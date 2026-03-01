"""
Tests for email routes — send, list, get, reply, move, mark-read, delete.
"""
import time
import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from agents.outlook_agent.src.main import create_app


@pytest.fixture
def app_with_tokens(dummy_token_store):
    import asyncio
    asyncio.get_event_loop().run_until_complete(
        dummy_token_store.set(
            "test_tenant", "user1",
            {"access_token": "fake-token", "refresh_token": "fake-refresh",
             "expires_at": int(time.time()) + 3600}
        )
    )
    application = create_app(default_tenant_id="test_tenant")
    application.state.token_store = dummy_token_store
    return application


@pytest.fixture
def client(app_with_tokens):
    return TestClient(app_with_tokens)


def test_send_email_success(client, monkeypatch):
    mock_send = AsyncMock(return_value={"status": "sent", "subject": "Hi", "to": ["a@b.com"]})
    monkeypatch.setattr(
        "agents.outlook_agent.src.services.msgraph_client.MicrosoftGraphClient.send_message",
        mock_send,
    )
    resp = client.post(
        "/outlook/email/send",
        json={"to": ["a@b.com"], "subject": "Hi", "body": "Hello"},
        headers={"X-Tenant-ID": "test_tenant", "X-User-ID": "user1"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_list_messages_success(client, monkeypatch):
    mock_list = AsyncMock(return_value={"value": [{"id": "m1", "subject": "Test"}]})
    monkeypatch.setattr(
        "agents.outlook_agent.src.services.msgraph_client.MicrosoftGraphClient.list_messages",
        mock_list,
    )
    resp = client.get(
        "/outlook/email/list",
        headers={"X-Tenant-ID": "test_tenant", "X-User-ID": "user1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["messages"][0]["subject"] == "Test"


def test_delete_message_success(client, monkeypatch):
    mock_delete = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "agents.outlook_agent.src.services.msgraph_client.MicrosoftGraphClient.delete_message",
        mock_delete,
    )
    resp = client.delete(
        "/outlook/email/msg123",
        headers={"X-Tenant-ID": "test_tenant", "X-User-ID": "user1"},
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


def test_mark_read_success(client, monkeypatch):
    mock_mark = AsyncMock(return_value={"message_id": "msg123", "is_read": True})
    monkeypatch.setattr(
        "agents.outlook_agent.src.services.msgraph_client.MicrosoftGraphClient.mark_as_read",
        mock_mark,
    )
    resp = client.post(
        "/outlook/email/mark-read",
        json={"message_id": "msg123", "is_read": True},
        headers={"X-Tenant-ID": "test_tenant", "X-User-ID": "user1"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
