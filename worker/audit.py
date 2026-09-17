"""Local audit read API; audit writes are mediated by the storage boundary."""
from fastapi import APIRouter, Depends
from worker.dak import current_user
from worker.store import get_store

router = APIRouter()

@router.get("/recent")
async def get_recent_audit(_user: str = Depends(current_user)):
    return get_store().data["audit"][-50:]

@router.get("/tickets/{ticket_id}")
async def get_ticket_audit(ticket_id: str, _user: str = Depends(current_user)):
    return [entry for entry in get_store().data["audit"] if entry["detail"].get("ticket_id") == ticket_id]

@router.get("/stats")
async def get_audit_stats(_user: str = Depends(current_user)):
    actions = [entry["action"] for entry in get_store().data["audit"]]
    return {"total_entries": len(actions), "actions": {action: actions.count(action) for action in set(actions)}}
