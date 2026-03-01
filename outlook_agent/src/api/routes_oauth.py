"""
OAuth routes for Outlook — Microsoft identity platform.
Mirrors gmail_agent routes_oauth.py pattern.

Endpoints:
  POST /outlook/oauth/init      → returns Microsoft login URL
  GET  /outlook/oauth/callback  → exchanges code for tokens
  POST /outlook/oauth/link-tokens → share tokens between users
"""

import time
from typing import Optional, Dict
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, Header

from agents.outlook_agent.src.config import settings
from agents.outlook_agent.src.models.schemas import OAuthInitRequest, OAuthInitResponse, LinkTokensRequest
from agents.outlook_agent.src.services.token_store import encode_state, decode_state

router = APIRouter(prefix="/outlook/oauth", tags=["oauth"])


async def _handle_oauth_callback(request: Request, code: str, state: str) -> Dict:
    """Exchange OAuth code for tokens and store them."""
    token_store = request.app.state.token_store
    decoded = decode_state(state)
    tenant_id = decoded.get("tenant_id")
    user_id = decoded.get("user_id")

    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing tenant_id in state")

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            settings.token_url,
            data={
                "code": code,
                "client_id": settings.client_id,
                "client_secret": settings.client_secret,
                "redirect_uri": settings.redirect_uri,
                "grant_type": "authorization_code",
                "scope": " ".join(settings.scopes),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        token_data = resp.json()

    expires_in = token_data.get("expires_in")
    if expires_in:
        token_data["expires_at"] = int(time.time()) + int(expires_in)

    await token_store.set(
        tenant_id=tenant_id,
        user_id=user_id,
        data={
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "scope": token_data.get("scope"),
            "expires_at": token_data.get("expires_at"),
        },
    )
    return {"success": True, "tenant_id": tenant_id, "user_id": user_id}


def _build_auth_url(payload: OAuthInitRequest) -> OAuthInitResponse:
    redirect_uri = str(payload.redirect_url or settings.redirect_uri)
    state_obj: Dict[str, str] = {"tenant_id": payload.tenant_id}
    if payload.user_id:
        state_obj["user_id"] = payload.user_id
    if payload.extra_state:
        state_obj.update(payload.extra_state)

    state = encode_state(state_obj)
    scope_str = " ".join(settings.scopes)

    query_params = {
        "client_id": settings.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "response_mode": "query",
        "scope": scope_str,
        "state": state,
        "prompt": "consent",
    }
    auth_url = f"{settings.auth_url}?{urlencode(query_params)}"
    return OAuthInitResponse(auth_url=auth_url, state=state, redirect_uri=redirect_uri)


@router.post("/init", response_model=OAuthInitResponse)
async def oauth_init(
    body: OAuthInitRequest,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """
    Initialize Microsoft OAuth flow.
    Returns the Microsoft login URL — open it in the browser to authenticate.
    """
    tenant_id = x_tenant_id or body.tenant_id
    user_id = x_user_id or body.user_id
    modified = OAuthInitRequest(
        tenant_id=tenant_id,
        user_id=user_id,
        redirect_url=body.redirect_url,
        extra_state=body.extra_state,
    )
    return _build_auth_url(modified)


@router.get("/callback")
async def oauth_callback(request: Request, code: str, state: str):
    """Microsoft redirects here after user signs in and consents."""
    return await _handle_oauth_callback(request, code, state)


@router.post("/link-tokens")
async def link_user_tokens(
    request: Request,
    body: LinkTokensRequest,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
):
    """Make target_user_id share tokens from source_user_id (shared mailbox support)."""
    tenant_id = x_tenant_id or request.app.state.default_tenant_id
    token_store = request.app.state.token_store
    try:
        await token_store.link_user_tokens(
            tenant_id=tenant_id,
            source_user_id=body.source_user_id,
            target_user_id=body.target_user_id,
        )
        return {
            "success": True,
            "message": f"Linked {body.target_user_id} → {body.source_user_id}",
            "tenant_id": tenant_id,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
