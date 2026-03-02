"""
Additional OAuth route tests covering the callback handler and link-tokens route
which bring routes_oauth.py from 66% to ~90%.
"""
import time
import json
import base64
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
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
    return TestClient(app, raise_server_exceptions=False)


def make_state(tenant_id="test_tenant", user_id="user1"):
    return encode_state({"tenant_id": tenant_id, "user_id": user_id})


def test_oauth_init_returns_auth_url(client):
    resp = client.post(
        "/outlook/oauth/init",
        json={"tenant_id": "test_tenant", "user_id": "user1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "auth_url" in data
    assert "login.microsoftonline.com" in data["auth_url"]
    assert "state" in data


def test_oauth_init_uses_header_over_body(client):
    resp = client.post(
        "/outlook/oauth/init",
        json={"tenant_id": "body_tenant", "user_id": "body_user"},
        headers={"X-Tenant-ID": "header_tenant", "X-User-ID": "header_user"},
    )
    data = resp.json()
    # state should encode header values
    decoded = json.loads(base64.urlsafe_b64decode(data["state"].encode()).decode())
    assert decoded["tenant_id"] == "header_tenant"
    assert decoded["user_id"] == "header_user"


def test_oauth_callback_success(client, dummy_token_store, monkeypatch):
    """Callback exchanges the code for tokens and stores them."""
    token_response = {
        "access_token": "access_tok",
        "refresh_token": "refresh_tok",
        "expires_in": 3600,
        "scope": "Files.Read",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = token_response
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    monkeypatch.setattr("agents.outlook_agent.src.api.routes_oauth.httpx.AsyncClient",
                        lambda **kw: mock_client)

    state = make_state()
    resp = client.get(f"/outlook/oauth/callback?code=authcode123&state={state}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["tenant_id"] == "test_tenant"


def test_oauth_callback_bad_state(client):
    """Callback with invalid state should return 400."""
    resp = client.get("/outlook/oauth/callback?code=abc&state=invalidstate")
    assert resp.status_code == 400


def test_link_tokens_success(client, dummy_token_store):
    """link-tokens copies tokens from source to target user."""
    import asyncio
    asyncio.get_event_loop().run_until_complete(
        dummy_token_store.set("test_tenant", "user_a",
                              {"access_token": "tok", "expires_at": 9999})
    )
    resp = client.post(
        "/outlook/oauth/link-tokens",
        json={"source_user_id": "user_a", "target_user_id": "user_b"},
        headers={"X-Tenant-ID": "test_tenant"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_link_tokens_missing_source(client):
    """link-tokens with nonexistent source returns 400."""
    resp = client.post(
        "/outlook/oauth/link-tokens",
        json={"source_user_id": "ghost", "target_user_id": "user_b"},
        headers={"X-Tenant-ID": "test_tenant"},
    )
    assert resp.status_code == 400
