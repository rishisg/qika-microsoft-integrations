"""
Folder management routes for OneDrive agent.

Endpoints:
  POST /onedrive/folders/create  → create a new folder
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Header

from agents.onedrive_agent.src.models.schemas import CreateFolderRequest

router = APIRouter(prefix="/onedrive/folders", tags=["folders"])


@router.post("/create")
async def create_folder(
    request: Request,
    body: CreateFolderRequest,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """Create a new folder in OneDrive root or inside a parent folder."""
    client = request.app.state.onedrive_client
    tenant_id = x_tenant_id or request.app.state.default_tenant_id
    user_id = x_user_id
    try:
        result = await client.create_folder(
            tenant_id=tenant_id, user_id=user_id,
            folder_name=body.folder_name, parent_path=body.parent_path,
        )
        return {
            "success": True,
            "folder_id": result.get("id"),
            "folder_name": result.get("name"),
            "web_url": result.get("webUrl"),
        }
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
