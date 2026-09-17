"""Human-approved, sandbox-only DAK flow."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from worker.schemas import DakPreviewOut
from worker.store import get_store

router = APIRouter()
security = HTTPBearer(auto_error=False)

def assert_scope(path):
    if not path.startswith(("blurred/", "outbox/")):
        get_store().audit("permission_denied", {"path_kind": path.split("/", 1)[0]})
        raise PermissionError("access denied to path")

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not credentials.credentials.startswith("local-"):
        raise HTTPException(status_code=403, detail="Authentication rejected")
    return credentials.credentials

@router.post("/preview/{ticket_id}", response_model=DakPreviewOut)
async def dak_preview(ticket_id: str, user_id: str = Depends(current_user)):
    store = get_store(); path = f"blurred/{ticket_id}/complaint.jpg"; assert_scope(path)
    message_id = str(uuid.uuid4())
    store.create_outbox({"id": message_id, "ticket_id": ticket_id, "status": "draft", "approved_by": None, "payload": {"blurred_signed_path_placeholder": store.get_signed(path), "order": ["image", "text", "pin"]}})
    store.audit("dak_preview", {"ticket_id": ticket_id, "actor": user_id})
    return DakPreviewOut(msg_id=message_id)

@router.post("/approve/{msg_id}")
async def dak_approve(msg_id: str, user_id: str = Depends(current_user)):
    message = get_store().update_outbox(msg_id, status="approved", approved_by=user_id)
    if not message:
        raise HTTPException(status_code=404, detail="Outbox message not found")
    get_store().audit("dak_approved", {"msg_id": msg_id, "actor": user_id})
    return {"success": True, "msg_id": msg_id}
