"""
OneDriveAgent — library version.
Inherits from BaseAgent. Used by Qika Brain via MCP.
Mirrors OutlookAgent pattern.
"""
import logging
from typing import Any, Dict, List, Optional

from qika_integrations_agents.core.base.agent_base import BaseAgent
from qika_integrations_agents.core.base.types import (
    AgentCategory, AgentState, AgentResponse,
    SearchResponse, CreateResponse, UpdateResponse, GetRecordResponse,
)


class OneDriveAgent(BaseAgent):
    @property
    def agent_name(self) -> str:
        return "onedrive"

    @property
    def agent_category(self) -> AgentCategory:
        return AgentCategory.STORAGE

    @property
    def supported_capabilities(self) -> List[str]:
        return [
            "list_files", "upload_file", "download_file",
            "get_file", "delete_file", "create_folder", "share_file",
            "get_drive_info",
        ]

    def __init__(self, tenant_id: str, credentials: Dict[str, Any],
                 config: Optional[Dict[str, Any]] = None,
                 logger: Optional[logging.Logger] = None):
        super().__init__(tenant_id, credentials, config, logger)
        self.user_id: Optional[str] = self.config.get("user_id")

        from agents.onedrive_agent.src.services.token_store import FileTokenStore
        from agents.onedrive_agent.src.services.onedrive_client import OneDriveGraphClient

        token_store = self.config.get("token_store") or FileTokenStore(
            path=self.config.get("token_store_path", "./local_secrets/onedrive_tokens.json")
        )
        self.token_store = token_store
        self.client = OneDriveGraphClient(
            token_store=token_store,
            client_id=self.credentials.get("client_id", ""),
            client_secret=self.credentials.get("client_secret", ""),
            redirect_uri=self.config.get("redirect_uri", "http://localhost:8011/onedrive/oauth/callback"),
            scopes=self.config.get("scopes", [
                "https://graph.microsoft.com/Files.ReadWrite.All",
                "offline_access",
            ]),
        )

    # ── Lifecycle ─────────────────────────────────────────────
    async def install(self, metadata=None):
        self._set_state(AgentState.INSTALLED)
        return {"status": "installed", "tenant_id": self.tenant_id}

    async def authorize(self, auth_code, redirect_uri):
        self._set_state(AgentState.AUTHORIZED)
        return {"status": "authorized"}

    async def validate(self):
        try:
            await self.client.get_drive_info(self.tenant_id, self.user_id)
            self._set_state(AgentState.VALIDATED)
            return {"status": "validated", "connected": True}
        except Exception as exc:
            self._set_state(AgentState.ERROR)
            return {"status": "error", "error": str(exc)}

    async def get_status(self):
        return {
            "agent": self.agent_name, "tenant_id": self.tenant_id,
            "state": self.state.value, "capabilities": self.supported_capabilities,
        }

    async def uninstall(self):
        await self.client.aclose()
        self._set_state(AgentState.UNINSTALLED)
        return {"status": "uninstalled"}

    # ── BaseAgent CRUD ────────────────────────────────────────
    async def search(self, module, filters=None, limit=20, **kwargs):
        try:
            folder_path = filters.get("folder_path") if filters else None
            result = await self.client.list_items(self.tenant_id, self.user_id, folder_path=folder_path)
            items = result.get("value", [])
            return SearchResponse(success=True, count=len(items), results=items)
        except Exception as exc:
            return SearchResponse(success=False, error={"message": str(exc)}, count=0, results=[])

    async def get_record(self, module, record_id, **kwargs):
        try:
            result = await self.client.get_item_metadata(self.tenant_id, self.user_id, record_id)
            return GetRecordResponse(success=True, record=result)
        except Exception as exc:
            return GetRecordResponse(success=False, error={"message": str(exc)}, record={})

    async def create_record(self, module, data, **kwargs):
        try:
            if module == "files":
                import base64
                content = base64.b64decode(data.get("content_base64", ""))
                result = await self.client.upload_file(
                    self.tenant_id, self.user_id,
                    file_name=data["file_name"], content=content,
                    folder_path=data.get("folder_path"),
                    mime_type=data.get("mime_type", "application/octet-stream"),
                )
                return CreateResponse(success=True, record_id=result.get("id", ""), record=result)
            elif module == "folders":
                result = await self.client.create_folder(
                    self.tenant_id, self.user_id,
                    folder_name=data["folder_name"], parent_path=data.get("parent_path"),
                )
                return CreateResponse(success=True, record_id=result.get("id", ""), record=result)
            raise ValueError(f"Unsupported module: {module}")
        except Exception as exc:
            return CreateResponse(success=False, error={"message": str(exc)}, record_id="")

    async def update_record(self, module, record_id, data, **kwargs):
        return UpdateResponse(success=False, error={"message": "Use share_file for permissions"}, record_id=record_id, updated_fields={})

    # ── Capabilities ──────────────────────────────────────────
    async def list_files(self, *, folder_path: Optional[str] = None) -> AgentResponse:
        try:
            result = await self.client.list_items(self.tenant_id, self.user_id, folder_path=folder_path)
            return AgentResponse(success=True, data=result, metadata={"count": len(result.get("value", []))})
        except Exception as exc:
            return AgentResponse(success=False, error={"message": str(exc)})

    async def upload_file(self, *, file_name: str, content: bytes, folder_path: Optional[str] = None, mime_type: str = "application/octet-stream") -> AgentResponse:
        try:
            result = await self.client.upload_file(self.tenant_id, self.user_id, file_name, content, folder_path, mime_type)
            return AgentResponse(success=True, data=result)
        except Exception as exc:
            return AgentResponse(success=False, error={"message": str(exc)})

    async def download_file(self, *, item_id: str) -> AgentResponse:
        try:
            content = await self.client.download_file(self.tenant_id, self.user_id, item_id)
            return AgentResponse(success=True, data={"item_id": item_id, "content": content, "size": len(content)})
        except Exception as exc:
            return AgentResponse(success=False, error={"message": str(exc)})

    async def delete_file(self, *, item_id: str) -> AgentResponse:
        try:
            await self.client.delete_item(self.tenant_id, self.user_id, item_id)
            return AgentResponse(success=True, data={"deleted": True, "item_id": item_id})
        except Exception as exc:
            return AgentResponse(success=False, error={"message": str(exc)})

    async def create_folder(self, *, folder_name: str, parent_path: Optional[str] = None) -> AgentResponse:
        try:
            result = await self.client.create_folder(self.tenant_id, self.user_id, folder_name, parent_path)
            return AgentResponse(success=True, data=result)
        except Exception as exc:
            return AgentResponse(success=False, error={"message": str(exc)})

    async def share_file(self, *, item_id: str, emails: List[str], role: str = "read") -> AgentResponse:
        try:
            result = await self.client.share_item(self.tenant_id, self.user_id, item_id, emails, role)
            return AgentResponse(success=True, data=result)
        except Exception as exc:
            return AgentResponse(success=False, error={"message": str(exc)})

    async def get_drive_info(self) -> AgentResponse:
        try:
            result = await self.client.get_drive_info(self.tenant_id, self.user_id)
            return AgentResponse(success=True, data=result)
        except Exception as exc:
            return AgentResponse(success=False, error={"message": str(exc)})
