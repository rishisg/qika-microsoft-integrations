"""
File routes for OneDrive agent.

Endpoints:
  GET  /onedrive/files/list      → list files/folders in root or path
  GET  /onedrive/files/{id}      → get file metadata
  POST /onedrive/files/upload    → upload file (base64 body)
  GET  /onedrive/files/{id}/download → download file (returns base64)
  DELETE /onedrive/files/{id}    → delete file or folder
  POST /onedrive/files/share     → share item with email addresses
  GET  /onedrive/files/drive-info → drive quota info
"""

import base64
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Header, Query
from fastapi.responses import Response

from agents.onedrive_agent.src.models.schemas import (
    UploadFileRequest, ShareItemRequest,
)

router = APIRouter(prefix="/onedrive/files", tags=["files"])


def _get_client(request: Request):
    return request.app.state.onedrive_client


def _resolve(request: Request, x_tenant_id, x_user_id):
    tenant_id = x_tenant_id or request.app.state.default_tenant_id
    return tenant_id, x_user_id


@router.get("/list")
async def list_items(
    request: Request,
    folder_path: Optional[str] = Query(default=None, description="Folder path e.g. 'Documents'. Empty = root."),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """List files and folders in OneDrive root or a specific folder."""
    client = _get_client(request)
    tenant_id, user_id = _resolve(request, x_tenant_id, x_user_id)
    try:
        result = await client.list_items(tenant_id=tenant_id, user_id=user_id, folder_path=folder_path)
        items = result.get("value", [])
        return {
            "success": True,
            "count": len(items),
            "folder": folder_path or "root",
            "items": [
                {
                    "id": i.get("id"),
                    "name": i.get("name"),
                    "size": i.get("size"),
                    "type": "folder" if "folder" in i else "file",
                    "modified": i.get("lastModifiedDateTime"),
                    "web_url": i.get("webUrl"),
                }
                for i in items
            ],
        }
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/drive-info")
async def get_drive_info(
    request: Request,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """Get OneDrive quota and drive information."""
    client = _get_client(request)
    tenant_id, user_id = _resolve(request, x_tenant_id, x_user_id)
    try:
        result = await client.get_drive_info(tenant_id=tenant_id, user_id=user_id)
        quota = result.get("quota", {})
        return {
            "success": True,
            "drive_id": result.get("id"),
            "drive_type": result.get("driveType"),
            "owner": result.get("owner", {}).get("user", {}).get("displayName"),
            "quota": {
                "total_gb": round(quota.get("total", 0) / 1e9, 2),
                "used_gb": round(quota.get("used", 0) / 1e9, 2),
                "remaining_gb": round(quota.get("remaining", 0) / 1e9, 2),
                "state": quota.get("state"),
            },
        }
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/upload")
async def upload_file(
    request: Request,
    body: UploadFileRequest,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """
    Upload a file to OneDrive.
    Send file content as base64-encoded string in `content_base64`.
    """
    client = _get_client(request)
    tenant_id, user_id = _resolve(request, x_tenant_id, x_user_id)
    try:
        file_bytes = base64.b64decode(body.content_base64)
        result = await client.upload_file(
            tenant_id=tenant_id,
            user_id=user_id,
            file_name=body.file_name,
            content=file_bytes,
            folder_path=body.folder_path,
            mime_type=body.mime_type,
        )
        return {
            "success": True,
            "file_id": result.get("id"),
            "file_name": result.get("name"),
            "size": result.get("size"),
            "web_url": result.get("webUrl"),
        }
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{item_id}/download")
async def download_file(
    request: Request,
    item_id: str,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """Download a file from OneDrive. Returns base64-encoded content."""
    client = _get_client(request)
    tenant_id, user_id = _resolve(request, x_tenant_id, x_user_id)
    try:
        file_bytes = await client.download_file(tenant_id=tenant_id, user_id=user_id, item_id=item_id)
        return {
            "success": True,
            "item_id": item_id,
            "content_base64": base64.b64encode(file_bytes).decode(),
            "size_bytes": len(file_bytes),
        }
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{item_id}")
async def get_file_metadata(
    request: Request,
    item_id: str,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """Get metadata for a file or folder by ID."""
    client = _get_client(request)
    tenant_id, user_id = _resolve(request, x_tenant_id, x_user_id)
    try:
        result = await client.get_item_metadata(tenant_id=tenant_id, user_id=user_id, item_id=item_id)
        return {"success": True, "item": result}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{item_id}")
async def delete_item(
    request: Request,
    item_id: str,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """Permanently delete a file or folder from OneDrive."""
    client = _get_client(request)
    tenant_id, user_id = _resolve(request, x_tenant_id, x_user_id)
    try:
        await client.delete_item(tenant_id=tenant_id, user_id=user_id, item_id=item_id)
        return {"success": True, "deleted": True, "item_id": item_id}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/share")
async def share_item(
    request: Request,
    body: ShareItemRequest,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """Share a OneDrive file or folder with specific email addresses."""
    client = _get_client(request)
    tenant_id, user_id = _resolve(request, x_tenant_id, x_user_id)
    try:
        result = await client.share_item(
            tenant_id=tenant_id, user_id=user_id,
            item_id=body.item_id, emails=body.emails,
            role=body.role, send_invitation=body.send_invitation,
        )
        return {"success": True, "shared_with": body.emails, "role": body.role, "result": result}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
