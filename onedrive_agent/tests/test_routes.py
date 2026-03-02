"""
Tests for OneDrive file and folder routes.
Covers: list, drive-info, upload, download, get metadata, delete, share, create folder.
"""
import base64
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from agents.onedrive_agent.src.main import create_app


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


# ── Drive info ───────────────────────────────────────────

def test_drive_info_success(client, monkeypatch):
    monkeypatch.setattr(
        "agents.onedrive_agent.src.services.onedrive_client.OneDriveGraphClient.get_drive_info",
        AsyncMock(return_value={
            "id": "d1", "driveType": "personal",
            "owner": {"user": {"displayName": "Test User"}},
            "quota": {"total": 5_000_000_000, "used": 500_000_000,
                      "remaining": 4_500_000_000, "state": "normal"}
        })
    )
    resp = client.get("/onedrive/files/drive-info", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["quota"]["total_gb"] == 5.0
    assert data["owner"] == "Test User"


def test_drive_info_no_auth(client, monkeypatch):
    monkeypatch.setattr(
        "agents.onedrive_agent.src.services.onedrive_client.OneDriveGraphClient.get_drive_info",
        AsyncMock(side_effect=ValueError("No tokens found"))
    )
    resp = client.get("/onedrive/files/drive-info", headers=HEADERS)
    assert resp.status_code == 401


# ── List files ───────────────────────────────────────────

def test_list_root(client, monkeypatch):
    monkeypatch.setattr(
        "agents.onedrive_agent.src.services.onedrive_client.OneDriveGraphClient.list_items",
        AsyncMock(return_value={"value": [
            {"id": "f1", "name": "Documents", "folder": {}, "size": 0,
             "lastModifiedDateTime": "2024-01-01", "webUrl": "https://..."},
            {"id": "f2", "name": "photo.jpg", "file": {}, "size": 2048,
             "lastModifiedDateTime": "2024-01-02", "webUrl": "https://..."},
        ]})
    )
    resp = client.get("/onedrive/files/list", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert data["items"][0]["type"] == "folder"
    assert data["items"][1]["type"] == "file"


def test_list_with_folder_path(client, monkeypatch):
    monkeypatch.setattr(
        "agents.onedrive_agent.src.services.onedrive_client.OneDriveGraphClient.list_items",
        AsyncMock(return_value={"value": []})
    )
    resp = client.get("/onedrive/files/list?folder_path=Documents", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["folder"] == "Documents"


def test_list_server_error(client, monkeypatch):
    monkeypatch.setattr(
        "agents.onedrive_agent.src.services.onedrive_client.OneDriveGraphClient.list_items",
        AsyncMock(side_effect=Exception("Graph error"))
    )
    resp = client.get("/onedrive/files/list", headers=HEADERS)
    assert resp.status_code == 500


# ── Upload ───────────────────────────────────────────────

def test_upload_success(client, monkeypatch):
    monkeypatch.setattr(
        "agents.onedrive_agent.src.services.onedrive_client.OneDriveGraphClient.upload_file",
        AsyncMock(return_value={"id": "item1", "name": "test.txt",
                                "size": 32, "webUrl": "https://..."})
    )
    body = {
        "file_name": "test.txt",
        "content_base64": base64.b64encode(b"Hello World").decode(),
        "mime_type": "text/plain",
    }
    resp = client.post("/onedrive/files/upload", json=body, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["file_name"] == "test.txt"


def test_upload_no_auth(client, monkeypatch):
    monkeypatch.setattr(
        "agents.onedrive_agent.src.services.onedrive_client.OneDriveGraphClient.upload_file",
        AsyncMock(side_effect=ValueError("No tokens found"))
    )
    body = {
        "file_name": "test.txt",
        "content_base64": base64.b64encode(b"Hello").decode(),
    }
    resp = client.post("/onedrive/files/upload", json=body, headers=HEADERS)
    assert resp.status_code == 401


# ── Download ─────────────────────────────────────────────

def test_download_success(client, monkeypatch):
    monkeypatch.setattr(
        "agents.onedrive_agent.src.services.onedrive_client.OneDriveGraphClient.download_file",
        AsyncMock(return_value=b"Hello from OneDrive!")
    )
    resp = client.get("/onedrive/files/item1/download", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    decoded = base64.b64decode(data["content_base64"])
    assert decoded == b"Hello from OneDrive!"


def test_download_not_found(client, monkeypatch):
    monkeypatch.setattr(
        "agents.onedrive_agent.src.services.onedrive_client.OneDriveGraphClient.download_file",
        AsyncMock(side_effect=Exception("Item not found"))
    )
    resp = client.get("/onedrive/files/bad_id/download", headers=HEADERS)
    assert resp.status_code == 500


# ── Get metadata ─────────────────────────────────────────

def test_get_metadata_success(client, monkeypatch):
    monkeypatch.setattr(
        "agents.onedrive_agent.src.services.onedrive_client.OneDriveGraphClient.get_item_metadata",
        AsyncMock(return_value={"id": "item1", "name": "test.txt", "size": 100})
    )
    resp = client.get("/onedrive/files/item1", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["item"]["name"] == "test.txt"


# ── Delete ───────────────────────────────────────────────

def test_delete_success(client, monkeypatch):
    monkeypatch.setattr(
        "agents.onedrive_agent.src.services.onedrive_client.OneDriveGraphClient.delete_item",
        AsyncMock(return_value=None)
    )
    resp = client.delete("/onedrive/files/item1", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] is True
    assert data["item_id"] == "item1"


def test_delete_no_auth(client, monkeypatch):
    monkeypatch.setattr(
        "agents.onedrive_agent.src.services.onedrive_client.OneDriveGraphClient.delete_item",
        AsyncMock(side_effect=ValueError("No tokens found"))
    )
    resp = client.delete("/onedrive/files/item1", headers=HEADERS)
    assert resp.status_code == 401


# ── Share ─────────────────────────────────────────────────

def test_share_success(client, monkeypatch):
    monkeypatch.setattr(
        "agents.onedrive_agent.src.services.onedrive_client.OneDriveGraphClient.share_item",
        AsyncMock(return_value={"value": [{"grantedTo": {"user": {"email": "b@c.com"}}}]})
    )
    body = {
        "item_id": "item1",
        "emails": ["b@c.com"],
        "role": "read",
        "send_invitation": True,
    }
    resp = client.post("/onedrive/files/share", json=body, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "b@c.com" in data["shared_with"]


def test_share_server_error(client, monkeypatch):
    monkeypatch.setattr(
        "agents.onedrive_agent.src.services.onedrive_client.OneDriveGraphClient.share_item",
        AsyncMock(side_effect=Exception("permission error"))
    )
    body = {"item_id": "item1", "emails": ["x@y.com"]}
    resp = client.post("/onedrive/files/share", json=body, headers=HEADERS)
    assert resp.status_code == 500


# ── Create folder ────────────────────────────────────────

def test_create_folder_success(client, monkeypatch):
    monkeypatch.setattr(
        "agents.onedrive_agent.src.services.onedrive_client.OneDriveGraphClient.create_folder",
        AsyncMock(return_value={"id": "fld1", "name": "Reports", "webUrl": "https://..."})
    )
    resp = client.post(
        "/onedrive/folders/create",
        json={"folder_name": "Reports"},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["folder_name"] == "Reports"


def test_create_folder_no_auth(client, monkeypatch):
    monkeypatch.setattr(
        "agents.onedrive_agent.src.services.onedrive_client.OneDriveGraphClient.create_folder",
        AsyncMock(side_effect=ValueError("No tokens found"))
    )
    resp = client.post(
        "/onedrive/folders/create",
        json={"folder_name": "Reports"},
        headers=HEADERS,
    )
    assert resp.status_code == 401


# ── Health check ─────────────────────────────────────────

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["agent"] == "onedrive"
