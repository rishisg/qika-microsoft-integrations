"""
Outlook Agent FastAPI app factory.
Mirrors gmail_agent/src/main.py pattern exactly.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from agents.outlook_agent.src.config import settings
from agents.outlook_agent.src.services.token_store import FileTokenStore
from agents.outlook_agent.src.services.msgraph_client import MicrosoftGraphClient
from agents.outlook_agent.src.api.routes_oauth import router as oauth_router, _handle_oauth_callback
from agents.outlook_agent.src.api.routes_email import router as email_router
from agents.outlook_agent.src.api.routes_folders import router as folders_router


def create_app(default_tenant_id: str) -> FastAPI:
    app = FastAPI(
        title="Outlook Agent",
        description=(
            "Qika integration agent for Microsoft Outlook email via Microsoft Graph API.\n\n"
            "**Auth:** Use `POST /outlook/oauth/init` to get a login URL, complete sign-in, "
            "then pass `X-Tenant-ID` and `X-User-ID` headers on all subsequent requests."
        ),
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Tenant/user context extraction middleware
    class TenantContextMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            request.state.tenant_id = (
                request.headers.get("X-Tenant-ID") or default_tenant_id
            )
            request.state.user_id = request.headers.get("X-User-ID")
            return await call_next(request)

    app.add_middleware(TenantContextMiddleware)

    # Wire up shared services
    token_store = FileTokenStore(
        path=settings.token_store_path,
        encryption_key=settings.encryption_key,
    )
    graph_client = MicrosoftGraphClient(
        token_store=token_store,
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        redirect_uri=settings.redirect_uri,
        scopes=settings.scopes,
    )

    app.state.token_store = token_store
    app.state.graph_client = graph_client
    app.state.default_tenant_id = default_tenant_id

    # Register routes
    app.include_router(oauth_router)
    app.include_router(email_router)
    app.include_router(folders_router)

    # Legacy callback path (matches Azure redirect URI)
    @app.get("/outlook/oauth/callback")
    async def oauth_callback_legacy(request: Request, code: str, state: str):
        """OAuth callback (matches Azure portal redirect URI)."""
        return await _handle_oauth_callback(request, code, state)

    @app.get("/health")
    async def health():
        return {"status": "ok", "agent": "outlook"}

    return app
