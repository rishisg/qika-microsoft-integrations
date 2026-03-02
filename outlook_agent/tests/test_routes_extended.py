"""Tests for Outlook folder routes and remaining email route operations."""
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
            {"access_token": "tok", "refresh_token": "ref",
             "expires_at": int(time.time()) + 3600}
        )
    )
    application = create_app(default_tenant_id="test_tenant")
    application.state.token_store = dummy_token_store
    return application


@pytest.fixture
def client(app_with_tokens):
    return TestClient(app_with_tokens)


HEADERS = {"X-Tenant-ID": "test_tenant", "X-User-ID": "user1"}


# ── Folder routes ────────────────────────────────────────

def test_list_folders_success(client, monkeypatch):
    mock_fn = AsyncMock(return_value={"value": [
        {"id": "f1", "displayName": "Inbox", "totalItemCount": 5, "unreadItemCount": 2},
        {"id": "f2", "displayName": "Sent Items", "totalItemCount": 3, "unreadItemCount": 0},
    ]})
    monkeypatch.setattr(
        "agents.outlook_agent.src.services.msgraph_client.MicrosoftGraphClient.list_mail_folders",
        mock_fn
    )
    resp = client.get("/outlook/folders/list", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["count"] == 2
    assert data["folders"][0]["name"] == "Inbox"


def test_list_folders_no_auth(client, monkeypatch):
    monkeypatch.setattr(
        "agents.outlook_agent.src.services.msgraph_client.MicrosoftGraphClient.list_mail_folders",
        AsyncMock(side_effect=ValueError("No tokens found"))
    )
    resp = client.get("/outlook/folders/list", headers=HEADERS)
    assert resp.status_code == 401


# ── Email routes (remaining operations) ─────────────────

def test_get_profile_success(client, monkeypatch):
    monkeypatch.setattr(
        "agents.outlook_agent.src.services.msgraph_client.MicrosoftGraphClient.get_me",
        AsyncMock(return_value={"id": "u1", "displayName": "Test", "mail": "t@hotmail.com"})
    )
    resp = client.get("/outlook/email/me", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["profile"]["mail"] == "t@hotmail.com"


def test_get_message_success(client, monkeypatch):
    monkeypatch.setattr(
        "agents.outlook_agent.src.services.msgraph_client.MicrosoftGraphClient.get_message",
        AsyncMock(return_value={"id": "msg1", "subject": "Hello"})
    )
    resp = client.get("/outlook/email/msg1", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["message"]["subject"] == "Hello"


def test_reply_success(client, monkeypatch):
    monkeypatch.setattr(
        "agents.outlook_agent.src.services.msgraph_client.MicrosoftGraphClient.reply_message",
        AsyncMock(return_value={"status": "replied", "message_id": "msg1"})
    )
    resp = client.post(
        "/outlook/email/reply",
        json={"message_id": "msg1", "body": "Thanks!"},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_move_success(client, monkeypatch):
    monkeypatch.setattr(
        "agents.outlook_agent.src.services.msgraph_client.MicrosoftGraphClient.move_message",
        AsyncMock(return_value={"id": "msg1"})
    )
    resp = client.post(
        "/outlook/email/move",
        json={"message_id": "msg1", "destination_folder_id": "folder_deleted"},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_list_messages_with_search(client, monkeypatch):
    monkeypatch.setattr(
        "agents.outlook_agent.src.services.msgraph_client.MicrosoftGraphClient.list_messages",
        AsyncMock(return_value={"value": [{"id": "m1", "subject": "Invoice"}]})
    )
    resp = client.get(
        "/outlook/email/list?search=Invoice&folder=inbox&max_results=5",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


def test_send_email_server_error(client, monkeypatch):
    monkeypatch.setattr(
        "agents.outlook_agent.src.services.msgraph_client.MicrosoftGraphClient.send_message",
        AsyncMock(side_effect=Exception("Graph API error"))
    )
    resp = client.post(
        "/outlook/email/send",
        json={"to": ["a@b.com"], "subject": "Hi", "body": "Test"},
        headers=HEADERS,
    )
    assert resp.status_code == 500


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["agent"] == "outlook"
