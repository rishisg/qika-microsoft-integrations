"""
Microsoft Graph API client for Outlook email operations.
All calls go through: https://graph.microsoft.com/v1.0/me/...
Handles token refresh automatically using the stored refresh_token.
"""

import time
import logging
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from agents.outlook_agent.src.config import settings

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

logger = logging.getLogger(__name__)


class MicrosoftGraphClient:
    """
    Async HTTP client for Microsoft Graph API.
    Wraps httpx.AsyncClient with token refresh, retry logic, and Outlook-specific methods.
    """

    def __init__(
        self,
        token_store,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: List[str],
    ):
        self.token_store = token_store
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=GRAPH_BASE,
                timeout=30.0,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _get_valid_token(self, tenant_id: str, user_id: Optional[str]) -> str:
        """Get access token, refreshing if expired."""
        token_data = await self.token_store.get(tenant_id, user_id)
        if not token_data:
            raise ValueError(f"No tokens found for tenant={tenant_id}, user={user_id}. Please OAuth first.")

        # Check if access token is expired (with 60s buffer)
        expires_at = token_data.get("expires_at", 0)
        if time.time() < (expires_at - 60):
            return token_data["access_token"]

        # Refresh the token
        logger.info(f"Refreshing access token for tenant={tenant_id}, user={user_id}")
        refreshed = await self._refresh_token(token_data["refresh_token"])
        refreshed["expires_at"] = int(time.time()) + refreshed.get("expires_in", 3600)
        # Keep old refresh_token if new one not provided
        if not refreshed.get("refresh_token"):
            refreshed["refresh_token"] = token_data["refresh_token"]
        await self.token_store.set(tenant_id, user_id, refreshed)
        return refreshed["access_token"]

    async def _refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Exchange refresh_token for new access_token."""
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
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # ──────────────────────────────────────────────────────
    # Email operations
    # ──────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        reraise=True,
    )
    async def list_messages(
        self,
        tenant_id: str,
        user_id: Optional[str],
        folder: str = "inbox",
        search: Optional[str] = None,
        max_results: int = 20,
        skip: int = 0,
    ) -> Dict[str, Any]:
        """List emails from a mail folder."""
        client = await self._get_client()
        headers = await self._auth_headers(tenant_id, user_id)

        params: Dict[str, Any] = {
            "$top": max_results,
            "$skip": skip,
            "$select": "id,subject,from,toRecipients,receivedDateTime,isRead,bodyPreview,hasAttachments",
            "$orderby": "receivedDateTime desc",
        }
        if search:
            params["$search"] = f'"{search}"'

        resp = await client.get(
            f"/me/mailFolders/{folder}/messages",
            headers=headers,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_message(
        self,
        tenant_id: str,
        user_id: Optional[str],
        message_id: str,
    ) -> Dict[str, Any]:
        """Get a single email by ID with full body."""
        client = await self._get_client()
        headers = await self._auth_headers(tenant_id, user_id)
        resp = await client.get(
            f"/me/messages/{message_id}",
            headers=headers,
            params={"$select": "id,subject,from,toRecipients,ccRecipients,bccRecipients,body,receivedDateTime,isRead,hasAttachments"},
        )
        resp.raise_for_status()
        return resp.json()

    async def send_message(
        self,
        tenant_id: str,
        user_id: Optional[str],
        to: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        body_type: str = "Text",
    ) -> Dict[str, Any]:
        """Send an email via Microsoft Graph /me/sendMail."""
        client = await self._get_client()
        headers = await self._auth_headers(tenant_id, user_id)

        def _recipients(emails: List[str]) -> List[Dict]:
            return [{"emailAddress": {"address": e}} for e in (emails or [])]

        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": body_type, "content": body},
                "toRecipients": _recipients(to),
                "ccRecipients": _recipients(cc or []),
                "bccRecipients": _recipients(bcc or []),
            },
            "saveToSentItems": True,
        }
        resp = await client.post("/me/sendMail", headers=headers, json=payload)
        resp.raise_for_status()
        # sendMail returns 202 Accepted with empty body
        return {"status": "sent", "subject": subject, "to": to}

    async def reply_message(
        self,
        tenant_id: str,
        user_id: Optional[str],
        message_id: str,
        body: str,
        body_type: str = "Text",
    ) -> Dict[str, Any]:
        """Reply to an email thread."""
        client = await self._get_client()
        headers = await self._auth_headers(tenant_id, user_id)
        payload = {"message": {}, "comment": body}
        resp = await client.post(
            f"/me/messages/{message_id}/reply",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        return {"status": "replied", "message_id": message_id}

    async def move_message(
        self,
        tenant_id: str,
        user_id: Optional[str],
        message_id: str,
        destination_folder_id: str,
    ) -> Dict[str, Any]:
        """Move email to another folder."""
        client = await self._get_client()
        headers = await self._auth_headers(tenant_id, user_id)
        resp = await client.post(
            f"/me/messages/{message_id}/move",
            headers=headers,
            json={"destinationId": destination_folder_id},
        )
        resp.raise_for_status()
        return resp.json()

    async def mark_as_read(
        self,
        tenant_id: str,
        user_id: Optional[str],
        message_id: str,
        is_read: bool = True,
    ) -> Dict[str, Any]:
        """Mark email as read or unread."""
        client = await self._get_client()
        headers = await self._auth_headers(tenant_id, user_id)
        resp = await client.patch(
            f"/me/messages/{message_id}",
            headers=headers,
            json={"isRead": is_read},
        )
        resp.raise_for_status()
        return {"message_id": message_id, "is_read": is_read}

    async def delete_message(
        self,
        tenant_id: str,
        user_id: Optional[str],
        message_id: str,
    ) -> None:
        """Permanently delete an email."""
        client = await self._get_client()
        headers = await self._auth_headers(tenant_id, user_id)
        resp = await client.delete(f"/me/messages/{message_id}", headers=headers)
        resp.raise_for_status()

    async def list_mail_folders(
        self,
        tenant_id: str,
        user_id: Optional[str],
    ) -> Dict[str, Any]:
        """List all mail folders (Inbox, Sent, Drafts, etc.)."""
        client = await self._get_client()
        headers = await self._auth_headers(tenant_id, user_id)
        resp = await client.get(
            "/me/mailFolders",
            headers=headers,
            params={"$select": "id,displayName,totalItemCount,unreadItemCount"},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_me(
        self,
        tenant_id: str,
        user_id: Optional[str],
    ) -> Dict[str, Any]:
        """Get current user profile."""
        client = await self._get_client()
        headers = await self._auth_headers(tenant_id, user_id)
        resp = await client.get(
            "/me",
            headers=headers,
            params={"$select": "id,displayName,mail,userPrincipalName"},
        )
        resp.raise_for_status()
        return resp.json()
