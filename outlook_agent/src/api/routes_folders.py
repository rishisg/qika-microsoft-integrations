"""
Mail folder routes for Outlook agent.

Endpoints:
  GET /outlook/folders/list  → list all mail folders (Inbox, Sent, Drafts, etc.)
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Header

router = APIRouter(prefix="/outlook/folders", tags=["folders"])


@router.get("/list")
async def list_folders(
    request: Request,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """List all Outlook mail folders (Inbox, Sent Items, Drafts, Deleted Items, etc.)."""
    client = request.app.state.graph_client
    tenant_id = x_tenant_id or request.app.state.default_tenant_id
    user_id = x_user_id
    try:
        result = await client.list_mail_folders(tenant_id=tenant_id, user_id=user_id)
        folders = result.get("value", [])
        return {
            "success": True,
            "count": len(folders),
            "folders": [
                {
                    "id": f.get("id"),
                    "name": f.get("displayName"),
                    "total_items": f.get("totalItemCount"),
                    "unread_items": f.get("unreadItemCount"),
                }
                for f in folders
            ],
        }
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
