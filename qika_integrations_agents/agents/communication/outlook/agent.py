"""
OutlookAgent — library version of the Outlook integration.
Inherits from BaseAgent. Used by Qika Brain via MCP.
Mirrors the GmailAgent pattern exactly.
"""

import logging
from typing import Any, Dict, List, Optional

from qika_integrations_agents.core.base.agent_base import BaseAgent
from qika_integrations_agents.core.base.types import (
    AgentCategory,
    AgentState,
    AgentResponse,
    SearchResponse,
    CreateResponse,
    UpdateResponse,
    GetRecordResponse,
)


class OutlookAgent(BaseAgent):
    """
    Qika integration agent for Microsoft Outlook.
    Talks to Microsoft Graph API via a shared MicrosoftGraphClient.
    """

    @property
    def agent_name(self) -> str:
        return "outlook"

    @property
    def agent_category(self) -> AgentCategory:
        return AgentCategory.COMMUNICATION

    @property
    def supported_capabilities(self) -> List[str]:
        return [
            "send_email",
            "reply_email",
            "read_messages",
            "list_messages",
            "get_message",
            "move",
            "mark_as_read",
            "delete",
            "list_folders",
        ]

    def __init__(
        self,
        tenant_id: str,
        credentials: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(tenant_id, credentials, config, logger)
        self.user_id: Optional[str] = self.config.get("user_id")

        # Lazy-import to avoid circular imports
        from agents.outlook_agent.src.services.token_store import FileTokenStore
        from agents.outlook_agent.src.services.msgraph_client import MicrosoftGraphClient

        token_store_path = self.config.get(
            "token_store_path", "./local_secrets/outlook_tokens.json"
        )
        token_store = self.config.get("token_store") or FileTokenStore(path=token_store_path)
        self.token_store = token_store

        self.client = MicrosoftGraphClient(
            token_store=token_store,
            client_id=self.credentials.get("client_id") or self.config.get("client_id", ""),
            client_secret=self.credentials.get("client_secret") or self.config.get("client_secret", ""),
            redirect_uri=self.config.get("redirect_uri", "http://localhost:8010/outlook/oauth/callback"),
            scopes=self.config.get("scopes", [
                "https://graph.microsoft.com/Mail.Read",
                "https://graph.microsoft.com/Mail.Send",
                "https://graph.microsoft.com/Mail.ReadWrite",
                "offline_access",
            ]),
        )

    # ── Lifecycle ─────────────────────────────────────────────

    async def install(self, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._set_state(AgentState.INSTALLED)
        return {"status": "installed", "tenant_id": self.tenant_id}

    async def authorize(self, auth_code: str, redirect_uri: str) -> Dict[str, Any]:
        self._set_state(AgentState.AUTHORIZED)
        return {"status": "authorized", "tenant_id": self.tenant_id}

    async def validate(self) -> Dict[str, Any]:
        try:
            await self.client.get_me(self.tenant_id, self.user_id)
            self._set_state(AgentState.VALIDATED)
            return {"status": "validated", "tenant_id": self.tenant_id, "connected": True}
        except Exception as exc:
            self._set_state(AgentState.ERROR)
            return {"status": "error", "tenant_id": self.tenant_id, "error": str(exc)}

    async def get_status(self) -> Dict[str, Any]:
        return {
            "agent": self.agent_name,
            "tenant_id": self.tenant_id,
            "state": self.state.value,
            "category": self.agent_category.value,
            "capabilities": self.supported_capabilities,
        }

    async def uninstall(self) -> Dict[str, Any]:
        await self.client.aclose()
        self._set_state(AgentState.UNINSTALLED)
        return {"status": "uninstalled", "tenant_id": self.tenant_id}

    # ── BaseAgent CRUD ────────────────────────────────────────

    async def search(
        self,
        module: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        **kwargs,
    ) -> SearchResponse:
        if module not in ["messages", "folders"]:
            return SearchResponse(
                success=False,
                error={"message": f"Module '{module}' not supported. Use 'messages' or 'folders'."},
                count=0, results=[],
            )
        try:
            if module == "messages":
                resp = await self.list_messages(
                    search=filters.get("search") if filters else None,
                    folder=filters.get("folder", "inbox") if filters else "inbox",
                    max_results=limit,
                )
                messages = resp.data.get("value", []) if resp.success else []
                return SearchResponse(success=resp.success, error=resp.error, count=len(messages), results=messages)
            else:
                resp = await self.list_folders()
                folders = resp.data.get("value", []) if resp.success else []
                return SearchResponse(success=resp.success, error=resp.error, count=len(folders), results=folders)
        except Exception as exc:
            return SearchResponse(success=False, error={"message": str(exc)}, count=0, results=[])

    async def get_record(self, module: str, record_id: str, **kwargs) -> GetRecordResponse:
        try:
            resp = await self.get_message(message_id=record_id)
            return GetRecordResponse(success=resp.success, error=resp.error, record=resp.data or {})
        except Exception as exc:
            return GetRecordResponse(success=False, error={"message": str(exc)}, record={})

    async def create_record(self, module: str, data: Dict[str, Any], **kwargs) -> CreateResponse:
        try:
            if module == "messages":
                resp = await self.send_email(
                    to=data.get("to", []),
                    subject=data.get("subject", ""),
                    body=data.get("body", ""),
                    cc=data.get("cc"),
                    bcc=data.get("bcc"),
                )
                record_id = resp.data.get("id", "") if resp.success else ""
                return CreateResponse(success=resp.success, error=resp.error, record_id=record_id, record=resp.data)
            raise ValueError(f"Unsupported module: {module}")
        except Exception as exc:
            return CreateResponse(success=False, error={"message": str(exc)}, record_id="")

    async def update_record(self, module: str, record_id: str, data: Dict[str, Any], **kwargs) -> UpdateResponse:
        try:
            if module == "messages":
                is_read = data.get("is_read")
                if is_read is not None:
                    resp = await self.mark_as_read(message_id=record_id, is_read=is_read)
                    return UpdateResponse(success=resp.success, error=resp.error, record_id=record_id, updated_fields=data)
            raise ValueError(f"Unsupported module or fields: {module}")
        except Exception as exc:
            return UpdateResponse(success=False, error={"message": str(exc)}, record_id=record_id, updated_fields={})

    # ── Capabilities ──────────────────────────────────────────

    async def send_email(
        self, *, to: List[str], subject: str, body: str,
        cc: Optional[List[str]] = None, bcc: Optional[List[str]] = None,
    ) -> AgentResponse:
        try:
            result = await self.client.send_message(
                tenant_id=self.tenant_id, user_id=self.user_id,
                to=to, subject=subject, body=body, cc=cc, bcc=bcc,
            )
            return AgentResponse(success=True, data=result)
        except Exception as exc:
            return AgentResponse(success=False, error={"message": str(exc)})

    async def reply_email(self, *, message_id: str, body: str) -> AgentResponse:
        try:
            result = await self.client.reply_message(
                tenant_id=self.tenant_id, user_id=self.user_id,
                message_id=message_id, body=body,
            )
            return AgentResponse(success=True, data=result)
        except Exception as exc:
            return AgentResponse(success=False, error={"message": str(exc)})

    async def list_messages(
        self, *, folder: str = "inbox", search: Optional[str] = None, max_results: int = 20
    ) -> AgentResponse:
        try:
            result = await self.client.list_messages(
                tenant_id=self.tenant_id, user_id=self.user_id,
                folder=folder, search=search, max_results=max_results,
            )
            return AgentResponse(success=True, data=result, metadata={"count": len(result.get("value", []))})
        except Exception as exc:
            return AgentResponse(success=False, error={"message": str(exc)})

    async def get_message(self, *, message_id: str) -> AgentResponse:
        try:
            result = await self.client.get_message(
                tenant_id=self.tenant_id, user_id=self.user_id, message_id=message_id
            )
            return AgentResponse(success=True, data=result)
        except Exception as exc:
            return AgentResponse(success=False, error={"message": str(exc)})

    async def mark_as_read(self, *, message_id: str, is_read: bool = True) -> AgentResponse:
        try:
            result = await self.client.mark_as_read(
                tenant_id=self.tenant_id, user_id=self.user_id,
                message_id=message_id, is_read=is_read,
            )
            return AgentResponse(success=True, data=result)
        except Exception as exc:
            return AgentResponse(success=False, error={"message": str(exc)})

    async def move(self, *, message_id: str, destination_folder_id: str) -> AgentResponse:
        try:
            result = await self.client.move_message(
                tenant_id=self.tenant_id, user_id=self.user_id,
                message_id=message_id, destination_folder_id=destination_folder_id,
            )
            return AgentResponse(success=True, data=result)
        except Exception as exc:
            return AgentResponse(success=False, error={"message": str(exc)})

    async def delete(self, *, message_id: str) -> AgentResponse:
        try:
            await self.client.delete_message(
                tenant_id=self.tenant_id, user_id=self.user_id, message_id=message_id
            )
            return AgentResponse(success=True, data={"deleted": True, "message_id": message_id})
        except Exception as exc:
            return AgentResponse(success=False, error={"message": str(exc)})

    async def list_folders(self) -> AgentResponse:
        try:
            result = await self.client.list_mail_folders(
                tenant_id=self.tenant_id, user_id=self.user_id
            )
            return AgentResponse(success=True, data=result)
        except Exception as exc:
            return AgentResponse(success=False, error={"message": str(exc)})
