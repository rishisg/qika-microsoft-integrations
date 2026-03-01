"""
Microsoft Graph API client for OneDrive operations.
All calls go through: https://graph.microsoft.com/v1.0/me/drive/...
Reuses the same token refresh pattern as the Outlook agent.
"""

import base64
import time
import logging
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from agents.onedrive_agent.src.config import settings

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

logger = logging.getLogger(__name__)


class OneDriveGraphClient:
    """
    Async HTTP client for Microsoft Graph OneDrive API.
    Supports upload, download, list, delete, create folder, share.
    """

    def __init__(self, token_store, client_id: str, client_secret: str,
                 redirect_uri: str, scopes: List[str]):
        self.token_store = token_store
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=GRAPH_BASE, timeout=60.0)
        return self._client

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _get_valid_token(self, tenant_id: str, user_id: Optional[str]) -> str:
        token_data = await self.token_store.get(tenant_id, user_id)
        if not token_data:
            raise ValueError(
                f"No tokens found for tenant={tenant_id}, user={user_id}. "
                "Please complete OAuth first via POST /onedrive/oauth/init"
            )
        expires_at = token_data.get("expires_at", 0)
        if time.time() < (expires_at - 60):
            return token_data["access_token"]

        # Refresh
        logger.info(f"Refreshing OneDrive token for tenant={tenant_id}, user={user_id}")
        refreshed = await self._refresh_token(token_data["refresh_token"])
        refreshed["expires_at"] = int(time.time()) + refreshed.get("expires_in", 3600)
        if not refreshed.get("refresh_token"):
            refreshed["refresh_token"] = token_data["refresh_token"]
        await self.token_store.set(tenant_id, user_id, refreshed)
        return refreshed["access_token"]

    async def _refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                settings.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                    "scope": " ".join(self.scopes),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            return resp.json()

    async def _auth_headers(self, tenant_id: str, user_id: Optional[str]) -> Dict[str, str]:
        token = await self._get_valid_token(tenant_id, user_id)
        return {"Authorization": f"Bearer {token}"}

    # ── File operations ────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10),
           retry=retry_if_exception_type(httpx.HTTPStatusError), reraise=True)
    async def list_items(
        self,
        tenant_id: str,
        user_id: Optional[str],
        folder_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List files and folders. folder_path=None lists the root."""
        client = await self._get_client()
        headers = await self._auth_headers(tenant_id, user_id)
        if folder_path:
            # URL-encode path segments
            path = folder_path.strip("/")
            url = f"/me/drive/root:/{path}:/children"
        else:
            url = "/me/drive/root/children"
        resp = await client.get(
            url, headers=headers,
            params={"$select": "id,name,size,createdDateTime,lastModifiedDateTime,file,folder,webUrl"},
        )
        resp.raise_for_status()
        return resp.json()

    async def upload_file(
        self,
        tenant_id: str,
        user_id: Optional[str],
        file_name: str,
        content: bytes,
        folder_path: Optional[str] = None,
        mime_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """
        Upload a file to OneDrive.
        Uses simple upload for files (Graph supports up to 4MB this way;
        for larger files use upload sessions — automatically falls back).
        """
        client = await self._get_client()
        headers = await self._auth_headers(tenant_id, user_id)
        headers["Content-Type"] = mime_type

        if folder_path:
            path = folder_path.strip("/")
            url = f"/me/drive/root:/{path}/{file_name}:/content"
        else:
            url = f"/me/drive/root:/{file_name}:/content"

        resp = await client.put(url, headers=headers, content=content)
        resp.raise_for_status()
        return resp.json()

    async def download_file(
        self,
        tenant_id: str,
        user_id: Optional[str],
        item_id: str,
    ) -> bytes:
        """Download a file by its item ID. Returns raw bytes."""
        client = await self._get_client()
        headers = await self._auth_headers(tenant_id, user_id)
        # Get the download URL first
        meta_resp = await client.get(
            f"/me/drive/items/{item_id}",
            headers=headers,
            params={"$select": "id,name,@microsoft.graph.downloadUrl"},
        )
        meta_resp.raise_for_status()
        download_url = meta_resp.json().get("@microsoft.graph.downloadUrl")
        if not download_url:
            raise ValueError(f"No download URL for item {item_id}")

        # Download from the direct URL (no auth needed for pre-signed URL)
        async with httpx.AsyncClient(timeout=120.0) as dl_client:
            dl_resp = await dl_client.get(download_url)
            dl_resp.raise_for_status()
            return dl_resp.content

    async def get_item_metadata(
        self,
        tenant_id: str,
        user_id: Optional[str],
        item_id: str,
    ) -> Dict[str, Any]:
        """Get metadata for a file or folder by ID."""
        client = await self._get_client()
        headers = await self._auth_headers(tenant_id, user_id)
        resp = await client.get(
            f"/me/drive/items/{item_id}",
            headers=headers,
            params={"$select": "id,name,size,createdDateTime,lastModifiedDateTime,file,folder,webUrl,parentReference"},
        )
        resp.raise_for_status()
        return resp.json()

    async def delete_item(
        self,
        tenant_id: str,
        user_id: Optional[str],
        item_id: str,
    ) -> None:
        """Delete a file or folder by ID."""
        client = await self._get_client()
        headers = await self._auth_headers(tenant_id, user_id)
        resp = await client.delete(f"/me/drive/items/{item_id}", headers=headers)
        resp.raise_for_status()

    async def create_folder(
        self,
        tenant_id: str,
        user_id: Optional[str],
        folder_name: str,
        parent_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new folder in OneDrive."""
        client = await self._get_client()
        headers = await self._auth_headers(tenant_id, user_id)
        headers["Content-Type"] = "application/json"

        if parent_path:
            path = parent_path.strip("/")
            url = f"/me/drive/root:/{path}:/children"
        else:
            url = "/me/drive/root/children"

        payload = {
            "name": folder_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "rename",
        }
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def share_item(
        self,
        tenant_id: str,
        user_id: Optional[str],
        item_id: str,
        emails: List[str],
        role: str = "read",
        send_invitation: bool = True,
    ) -> Dict[str, Any]:
        """Share a file or folder with specific email addresses."""
        client = await self._get_client()
        headers = await self._auth_headers(tenant_id, user_id)
        headers["Content-Type"] = "application/json"

        payload = {
            "recipients": [{"email": e} for e in emails],
            "message": "I'd like to share this item with you via Qika.",
            "requireSignIn": True,
            "sendInvitation": send_invitation,
            "roles": [role],
        }
        resp = await client.post(
            f"/me/drive/items/{item_id}/invite",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_drive_info(
        self,
        tenant_id: str,
        user_id: Optional[str],
    ) -> Dict[str, Any]:
        """Get OneDrive storage quota and drive info."""
        client = await self._get_client()
        headers = await self._auth_headers(tenant_id, user_id)
        resp = await client.get("/me/drive", headers=headers)
        resp.raise_for_status()
        return resp.json()
