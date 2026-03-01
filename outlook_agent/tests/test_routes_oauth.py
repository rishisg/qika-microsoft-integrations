"""
Tests for OAuth routes — init, callback, link-tokens.
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from agents.outlook_agent.src.main import create_app
from agents.outlook_agent.src.services.token_store import encode_state


@pytest.fixture
def app(dummy_token_store):
    application = create_app(default_tenant_id="test_tenant")
    application.state.token_store = dummy_token_store
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


def test_oauth_init_returns_auth_url(client):
    resp = client.post(
        "/outlook/oauth/init",
        json={"tenant_id": "tenant1", "user_id": "user1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "auth_url" in data
    assert "login.microsoftonline.com" in data["auth_url"]
    assert "state" in data


def test_oauth_init_header_overrides_body(client):
    resp = client.post(
        "/outlook/oauth/init",
        json={"tenant_id": "from_body", "user_id": "body_user"},
        headers={"X-Tenant-ID": "from_header", "X-User-ID": "header_user"},
    )
    assert resp.status_code == 200
    # State should encode header values
    data = resp.json()
    import base64, json
    decoded = json.loads(base64.urlsafe_b64decode(data["state"]))
    assert decoded["tenant_id"] == "from_header"
    assert decoded["user_id"] == "header_user"


def test_link_tokens_success(client, dummy_token_store):
    import asyncio
    asyncio.get_event_loop().run_until_complete(
        dummy_token_store.set("test_tenant", "user_a", {"access_token": "tok"})
    )
    resp = client.post(
        "/outlook/oauth/link-tokens",
        json={"source_user_id": "user_a", "target_user_id": "user_b"},
        headers={"X-Tenant-ID": "test_tenant"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_link_tokens_missing_source(client):
    resp = client.post(
        "/outlook/oauth/link-tokens",
        json={"source_user_id": "ghost", "target_user_id": "user_b"},
        headers={"X-Tenant-ID": "test_tenant"},
    )
    assert resp.status_code == 400
