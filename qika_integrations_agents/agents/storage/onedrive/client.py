"""
OneDrive API client wrapping Microsoft Graph API v1.0.
Includes basic retry/backoff handling for rate limits and transient errors.
"""

from typing import Any, Dict, Optional
import logging
import asyncio
import httpx

from qika_integrations_agents.core.base.client_base import BaseAPIClient
from qika_integrations_agents.agents.storage.onedrive.auth.oauth import refresh_access_token, is_token_expiring


logger = logging.getLogger(__name__)


RETRYABLE_STATUS = {429, 500, 502, 503, 504}
RETRYABLE_REASONS = {
    "throttled",
    "serviceUnavailable",
    "internalServerError",
}


class OneDriveAPIClient(BaseAPIClient):
    """
    Minimal client for OneDrive using Microsoft Graph API v1.0.
    """

    def __init__(
        self,
        base_url: str,
        credentials: Dict[str, Any],
        rate_limiter: Optional[Any] = None,
        retry_strategy: Optional[Any] = None,
        logger: Optional[logging.Logger] = None,
        max_retries: int = 5,
        backoff_base: float = 1.0,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        super().__init__(
            base_url=base_url,
            credentials=credentials,
            rate_limiter=rate_limiter,
            retry_strategy=retry_strategy,
            logger=logger,
        )
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.client_id = client_id
        self.client_secret = client_secret

    def get_auth_headers(self) -> Dict[str, str]:
        access_token = self.credentials.get("access_token")
        if not access_token:
            raise ValueError("Missing access_token for OneDrive API calls")
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        content: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        # Merge auth headers
        request_headers = self.get_auth_headers()
        if headers:
            request_headers.update(headers)

        attempt = 0
        last_exc: Optional[Exception] = None

        while attempt <= self.max_retries:
            try:
                # Check if token needs refresh before request
                if is_token_expiring(self.credentials):
                    await self._maybe_refresh_token()

                response = await self._client.request(
                    method, url, params=params, json=json, headers=request_headers, content=content
                )
                if response.status_code == 401:
                    # Try refresh once if possible, then retry.
                    if await self._maybe_refresh_token():
                        request_headers = self.get_auth_headers()
                        if headers:
                            request_headers.update(headers)
                        attempt += 1
                        continue
                    response.raise_for_status()

                if response.status_code in RETRYABLE_STATUS:
                    # Inspect body for Microsoft-specific reasons
                    try:
                        body = response.json()
                    except Exception:
                        body = {}
                    error = body.get("error", {})
                    reason = error.get("code") or error.get("message")
                    if self._should_retry(response.status_code, reason):
                        delay = self._compute_backoff(attempt, response)
                        self.logger.warning(
                            f"Retryable error {response.status_code} reason={reason}, attempt={attempt}, delay={delay}"
                        )
                        await asyncio.sleep(delay)
                        attempt += 1
                        continue

                response.raise_for_status()
                try:
                    return response.json()
                except Exception:
                    return {}

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status = exc.response.status_code
                body = {}
                try:
                    body = exc.response.json()
                except Exception:
                    pass
                error = body.get("error", {})
                reason = error.get("code") or error.get("message")
                if status in RETRYABLE_STATUS or self._should_retry(status, reason):
                    if attempt < self.max_retries:
                        delay = self._compute_backoff(attempt, exc.response)
                        self.logger.warning(
                            f"Retry {attempt} for {method} {url} status={status} reason={reason} delay={delay}"
                        )
                        await asyncio.sleep(delay)
                        attempt += 1
                        continue
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    delay = self._compute_backoff(attempt, None)
                    self.logger.warning(f"Retry {attempt} for {method} {url} exception={exc} delay={delay}")
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue
                raise

        if last_exc:
            raise last_exc
        raise RuntimeError("Request failed without exception")

    async def _maybe_refresh_token(self) -> bool:
        refresh_token = self.credentials.get("refresh_token")
        if not refresh_token or not self.client_id or not self.client_secret:
            return False
        try:
            new_tokens = await refresh_access_token(
                client_id=self.client_id,
                client_secret=self.client_secret,
                refresh_token=refresh_token,
                http_client=self._client,
            )
            self.credentials.update(new_tokens)
            return True
        except Exception as exc:
            self.logger.error(f"Token refresh failed: {exc}", exc_info=True)
            return False

    @staticmethod
    def _should_retry(status: int, reason: Optional[str]) -> bool:
        if status in RETRYABLE_STATUS:
            return True
        if reason and reason in RETRYABLE_REASONS:
            return True
        return False

    def _compute_backoff(self, attempt: int, response: Optional[httpx.Response]) -> float:
        # Honor Retry-After if present
        retry_after = None
        if response:
            retry_after_hdr = response.headers.get("Retry-After")
            if retry_after_hdr:
                try:
                    retry_after = float(retry_after_hdr)
                except ValueError:
                    retry_after = None
        if retry_after is not None:
            return max(retry_after, 0.0)
        # exponential backoff with cap ~60s
        delay = self.backoff_base * (2 ** attempt)
        return min(delay, 60.0)

    # -------- Files & Search --------
    async def search_files(self, q: Optional[str] = None, page_size: int = 200, skip_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Search files using Microsoft Graph search.
        Note: Graph API search is different from Google Drive - uses $search parameter.
        """
        if q:
            path = f"/me/drive/root/search(q='{q}')"
        else:
            path = "/me/drive/root/children"
        params = {"$top": page_size}
        if skip_token:
            params["$skipToken"] = skip_token
        url = f"{self.base_url}{path}"
        return await self._request("GET", url, params=params)

    async def get_file(self, file_id: str) -> Dict[str, Any]:
        """Get a file/folder by ID."""
        url = f"{self.base_url}/me/drive/items/{file_id}"
        return await self._request("GET", url)

    async def list_children(self, folder_id: str = "root", page_size: int = 200, skip_token: Optional[str] = None) -> Dict[str, Any]:
        """List children of a folder."""
        if folder_id == "root":
            path = "/me/drive/root/children"
        else:
            path = f"/me/drive/items/{folder_id}/children"
        params = {"$top": page_size}
        if skip_token:
            params["$skipToken"] = skip_token
        url = f"{self.base_url}{path}"
        return await self._request("GET", url, params=params)

    # -------- Permissions --------
    async def list_permissions(self, file_id: str) -> Dict[str, Any]:
        """List permissions for a file/folder."""
        url = f"{self.base_url}/me/drive/items/{file_id}/permissions"
        return await self._request("GET", url)

    # -------- Versions --------
    async def list_versions(self, file_id: str) -> Dict[str, Any]:
        """List versions (history) for a file."""
        url = f"{self.base_url}/me/drive/items/{file_id}/versions"
        return await self._request("GET", url)

    # -------- Delta query (for sync) --------
    async def get_delta(self, token: Optional[str] = None) -> Dict[str, Any]:
        """
        Get changes using delta query.
        Microsoft Graph uses delta queries instead of changes feed.
        """
        if token:
            path = f"/me/drive/root/delta?token={token}"
        else:
            path = "/me/drive/root/delta"
        url = f"{self.base_url}{path}"
        return await self._request("GET", url)

    # -------- Write Operations --------
    async def create_file(
        self,
        name: str,
        parent_id: Optional[str] = None,
        content: Optional[bytes] = None,
        content_type: Optional[str] = None,
        is_folder: bool = False,
    ) -> Dict[str, Any]:
        """Create a file or folder."""
        if is_folder:
            body = {"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "rename"}
        else:
            body = {"name": name, "@microsoft.graph.conflictBehavior": "rename"}

        if parent_id and parent_id != "root":
            path = f"/me/drive/items/{parent_id}/children"
        else:
            path = "/me/drive/root/children"

        if content is not None:
            # First create the file metadata
            created = await self._request("POST", f"{self.base_url}{path}", json=body)
            item_id = created.get("id")
            if not item_id:
                raise ValueError("Failed to create file")
            # Then upload content
            upload_url = f"{self.base_url}/me/drive/items/{item_id}/content"
            headers = {"Content-Type": content_type or "application/octet-stream"}
            return await self._request("PUT", upload_url, headers=headers, content=content)
        else:
            return await self._request("POST", f"{self.base_url}{path}", json=body)

    async def update_file(
        self,
        file_id: str,
        name: Optional[str] = None,
        content: Optional[bytes] = None,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a file's metadata and/or content."""
        if content is not None:
            upload_url = f"{self.base_url}/me/drive/items/{file_id}/content"
            headers = {"Content-Type": content_type or "application/octet-stream"}
            return await self._request("PUT", upload_url, headers=headers, content=content)
        elif name:
            body = {"name": name}
            return await self._request("PATCH", f"{self.base_url}/me/drive/items/{file_id}", json=body)
        else:
            raise ValueError("Either name or content must be provided")

    async def delete_file(self, file_id: str) -> None:
        """Delete a file/folder."""
        url = f"{self.base_url}/me/drive/items/{file_id}"
        headers = self.get_auth_headers()
        response = await self._client.request("DELETE", url, headers=headers)
        if response.status_code == 401:
            if await self._maybe_refresh_token():
                headers = self.get_auth_headers()
                response = await self._client.request("DELETE", url, headers=headers)
            else:
                response.raise_for_status()
        response.raise_for_status()
