"""OneDrive Agent FastAPI app factory."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from agents.onedrive_agent.src.config import settings
from agents.onedrive_agent.src.services.token_store import FileTokenStore
from agents.onedrive_agent.src.services.onedrive_client import OneDriveGraphClient
from agents.onedrive_agent.src.api.routes_oauth import router as oauth_router, _handle_oauth_callback
from agents.onedrive_agent.src.api.routes_files import router as files_router
from agents.onedrive_agent.src.api.routes_folders import router as folders_router


def create_app(default_tenant_id: str) -> FastAPI:
    app = FastAPI(
        title="OneDrive Agent",
        description=(
            "Qika integration agent for Microsoft OneDrive via Microsoft Graph API.\n\n"
            "**Auth:** Use `POST /onedrive/oauth/init` to get a login URL, complete sign-in, "
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

    class TenantContextMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            request.state.tenant_id = request.headers.get("X-Tenant-ID") or default_tenant_id
            request.state.user_id = request.headers.get("X-User-ID")
            return await call_next(request)

    app.add_middleware(TenantContextMiddleware)

    token_store = FileTokenStore(
        path=settings.token_store_path,
        encryption_key=settings.encryption_key,
    )
    onedrive_client = OneDriveGraphClient(
        token_store=token_store,
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        redirect_uri=settings.redirect_uri,
        scopes=settings.scopes,
    )

    app.state.token_store = token_store
    app.state.onedrive_client = onedrive_client
    app.state.default_tenant_id = default_tenant_id

    app.include_router(oauth_router)
    app.include_router(files_router)
    app.include_router(folders_router)

    @app.get("/onedrive/oauth/callback")
    async def oauth_callback_legacy(request: Request, code: str, state: str):
        """OAuth callback (matches Azure portal redirect URI)."""
        return await _handle_oauth_callback(request, code, state)

    @app.get("/health")
    async def health():
        return {"status": "ok", "agent": "onedrive"}

    return app
