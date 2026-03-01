"""
OutlookAdapter — MCP adapter for Outlook communication.
Translates canonical communication actions → Microsoft Graph via MCPClient.
Mirrors GmailAdapter pattern exactly.
"""

from typing import Any, Dict, List
from qika_integrations_agents.adapters.communication.base import BaseCommunicationAdapter


class OutlookAdapter(BaseCommunicationAdapter):
    """Adapter for Outlook / Microsoft Graph email provider."""

    @property
    def provider_name(self) -> str:
        return "outlook"

    async def send_email(self, data: Dict[str, Any]) -> Dict[str, Any]:
        from qika_integrations_agents.errors.canonical_exceptions import CanonicalError
        from qika_integrations_agents.errors.codes import MCPErrorCode
        try:
            request = self.mcp_client.MCPActionRequest(
                tenant_id=self.tenant_id,
                provider=self.provider_name,
                provider_action="send_email",
                oauth_connection_id=self.oauth_connection_id,
                inputs=data,
            )
            response = await self.mcp_client.execute_action(request)
            return self.normalize_delivery_status(response.output)
        except Exception as exc:
            raise CanonicalError(
                code=MCPErrorCode.UNKNOWN,
                message=f"Outlook send_email failed: {str(exc)}",
                retryable=False,
                details={"adapter": "outlook", "operation": "send_email"},
            ) from exc

    async def send_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Outlook does not support chat messages — use Teams adapter instead."""
        raise NotImplementedError("Outlook does not support chat. Use TeamsAdapter for chat.")

    async def read_messages(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        from qika_integrations_agents.errors.canonical_exceptions import CanonicalError
        from qika_integrations_agents.errors.codes import MCPErrorCode
        try:
            request = self.mcp_client.MCPActionRequest(
                tenant_id=self.tenant_id,
                provider=self.provider_name,
                provider_action="read_messages",
                oauth_connection_id=self.oauth_connection_id,
                inputs=filters or {},
            )
            response = await self.mcp_client.execute_action(request)
            return response.output.get("value", [])
        except Exception as exc:
            raise CanonicalError(
                code=MCPErrorCode.UNKNOWN,
                message=f"Outlook read_messages failed: {str(exc)}",
                retryable=False,
                details={"adapter": "outlook", "operation": "read_messages"},
            ) from exc

    def render_template(self, template: str, context: Dict[str, Any]) -> str:
        return template.format(**context)

    def handle_attachments(self, attachments: Any) -> Any:
        return attachments

    def map_thread(self, provider_thread: Any) -> Dict[str, Any]:
        return {"thread_id": provider_thread.get("conversationId")}

    def normalize_delivery_status(self, provider_status: Any) -> str:
        if isinstance(provider_status, dict):
            return provider_status.get("status", "unknown")
        return str(provider_status)
