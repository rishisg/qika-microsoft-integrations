"""
Email routes for Outlook agent.

Endpoints:
  POST /outlook/email/send       → send email
  GET  /outlook/email/list       → list messages
  GET  /outlook/email/{id}       → get single message
  POST /outlook/email/reply      → reply to message
  POST /outlook/email/move       → move to folder
  POST /outlook/email/mark-read  → mark read/unread
  DELETE /outlook/email/{id}     → delete message
  GET  /outlook/email/me         → get current user profile
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Header, Query

from agents.outlook_agent.src.models.schemas import (
    SendEmailRequest,
    SendEmailResponse,
    ReplyEmailRequest,
    ListMessagesRequest,
    MoveMessageRequest,
    MarkReadRequest,
)

router = APIRouter(prefix="/outlook/email", tags=["email"])


def _get_client(request: Request):
    return request.app.state.graph_client


def _resolve(request: Request, x_tenant_id, x_user_id):
    tenant_id = x_tenant_id or request.app.state.default_tenant_id
    user_id = x_user_id
    return tenant_id, user_id


@router.post("/send", response_model=SendEmailResponse)
async def send_email(
    request: Request,
    body: SendEmailRequest,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """Send an email via Outlook / Microsoft Graph."""
    client = _get_client(request)
    tenant_id, user_id = _resolve(request, x_tenant_id, x_user_id)
    try:
        result = await client.send_message(
            tenant_id=tenant_id,
            user_id=user_id,
            to=body.to,
            subject=body.subject,
            body=body.body,
            cc=body.cc,
            bcc=body.bcc,
            body_type=body.body_type,
        )
        return SendEmailResponse(
            success=True,
            status=result.get("status", "sent"),
            subject=body.subject,
            to=body.to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/list")
async def list_messages(
    request: Request,
    folder: str = Query(default="inbox"),
    search: Optional[str] = Query(default=None),
    max_results: int = Query(default=20, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """List emails from a mail folder (default: inbox)."""
    client = _get_client(request)
    tenant_id, user_id = _resolve(request, x_tenant_id, x_user_id)
    try:
        result = await client.list_messages(
            tenant_id=tenant_id,
            user_id=user_id,
            folder=folder,
            search=search,
            max_results=max_results,
            skip=skip,
        )
        messages = result.get("value", [])
        return {
            "success": True,
            "count": len(messages),
            "messages": messages,
            "next_link": result.get("@odata.nextLink"),
        }
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/me")
async def get_profile(
    request: Request,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """Get the currently authenticated Microsoft user's profile."""
    client = _get_client(request)
    tenant_id, user_id = _resolve(request, x_tenant_id, x_user_id)
    try:
        result = await client.get_me(tenant_id=tenant_id, user_id=user_id)
        return {"success": True, "profile": result}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{message_id}")
async def get_message(
    request: Request,
    message_id: str,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """Get a specific email by its ID."""
    client = _get_client(request)
    tenant_id, user_id = _resolve(request, x_tenant_id, x_user_id)
    try:
        result = await client.get_message(
            tenant_id=tenant_id, user_id=user_id, message_id=message_id
        )
        return {"success": True, "message": result}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/reply")
async def reply_message(
    request: Request,
    body: ReplyEmailRequest,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """Reply to an email."""
    client = _get_client(request)
    tenant_id, user_id = _resolve(request, x_tenant_id, x_user_id)
    try:
        result = await client.reply_message(
            tenant_id=tenant_id,
            user_id=user_id,
            message_id=body.message_id,
            body=body.body,
            body_type=body.body_type,
        )
        return {"success": True, **result}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/move")
async def move_message(
    request: Request,
    body: MoveMessageRequest,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """Move an email to a different folder."""
    client = _get_client(request)
    tenant_id, user_id = _resolve(request, x_tenant_id, x_user_id)
    try:
        result = await client.move_message(
            tenant_id=tenant_id,
            user_id=user_id,
            message_id=body.message_id,
            destination_folder_id=body.destination_folder_id,
        )
        return {"success": True, "moved_message": result}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/mark-read")
async def mark_as_read(
    request: Request,
    body: MarkReadRequest,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """Mark an email as read or unread."""
    client = _get_client(request)
    tenant_id, user_id = _resolve(request, x_tenant_id, x_user_id)
    try:
        result = await client.mark_as_read(
            tenant_id=tenant_id,
            user_id=user_id,
            message_id=body.message_id,
            is_read=body.is_read,
        )
        return {"success": True, **result}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{message_id}")
async def delete_message(
    request: Request,
    message_id: str,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """Permanently delete an email."""
    client = _get_client(request)
    tenant_id, user_id = _resolve(request, x_tenant_id, x_user_id)
    try:
        await client.delete_message(
            tenant_id=tenant_id, user_id=user_id, message_id=message_id
        )
        return {"success": True, "deleted": True, "message_id": message_id}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
