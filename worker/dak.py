"""
DAK (Direct Agent Komunikasi) module for SAKSHI worker
Handles DAK preview and approval endpoints
"""
import os
import json
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from worker.schemas import DakPreviewOut
from supabase import create_client, Client

router = APIRouter()

# Initialize Supabase client
supabase: Client = None

def init_supabase():
    global supabase
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if supabase_url and supabase_key:
        supabase = create_client(supabase_url, supabase_key)
    else:
        raise ValueError("Supabase URL and service role key must be set")

# Initialize on module load
try:
    init_supabase()
except Exception as e:
    print(f"Warning: Could not initialize Supabase client: {e}")

# Security dependency
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
security = HTTPBearer()

async def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify authenticated user (staff)"""
    token = credentials.credentials
    # In real implementation, verify token against Supabase auth
    # For now, just check if present
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    return token

async def verify_service_role(x_supabase_role: Optional[str] = None):
    """Verify service role (for privileged operations)"""
    if x_supabase_role != "service_role":
        raise HTTPException(status_code=403, detail="Service role required")
    return x_supabase_role

def assert_scope(path: str) -> None:
    """
    Helper function to check if path is within allowed scope
    Raises PermissionError if path is not in blurred/outbox buckets
    """
    allowed_prefixes = ["blurred/", "outbox/"]
    if not any(path.startswith(prefix) for prefix in allowed_prefixes):
        raise PermissionError(f"Access denied to path: {path}")
    
    # In real implementation, this would also audit 'permission_denied' on failure
    # For now, we just raise the exception

@router.post("/preview/{ticket_id}", response_model=DakPreviewOut)
async def dak_preview(
    ticket_id: str,
    x_supabase_role: str = Depends(verify_service_role)
):
    """
    Create DAK preview:
    - Create outbox_msgs row with status 'draft'
    - Payload includes blurred_signed_path_placeholder, text_summary, lat, lng, packet_id, order
    - Audit 'dak_preview'
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not initialized")
    
    try:
        # Get ticket details
        ticket_resp = supabase.table("tickets").select(
            "id, loc_lat, loc_lng"
        ).eq("id", ticket_id).single().execute()
        
        if not ticket_resp.data:
            raise HTTPException(status_code=404, detail="Ticket not found")
        
        ticket = ticket_resp.data
        
        # Get packet draft from ticket (would be stored in ticket or separate table)
        # For now, generate a placeholder
        packet_id = str(uuid.uuid4())
        
        # Create blurred signed path placeholder (would be real signed URL in implementation)
        blurred_path = f"blurred/{ticket_id}/complaint_blurred.jpg"
        
        # Verify scope (would raise PermissionError if invalid)
        try:
            assert_scope(blurred_path)
        except PermissionError as e:
            # Audit permission denied
            if supabase:
                supabase.table("audit_log").insert({
                    "actor": "system",
                    "action": "permission_denied",
                    "detail": {
                        "ticket_id": ticket_id,
                        "path": blurred_path,
                        "error": str(e)
                    }
                }).execute()
            raise HTTPException(status_code=403, detail=str(e))
        
        # Create outbox message
        outbox_msg = {
            "id": str(uuid.uuid4()),
            "ticket_id": ticket_id,
            "payload": {
                "blurred_signed_path_placeholder": f"https://storage.example.com/{blurred_path}?token=placeholder",
                "text_summary": "Complaint summary from analysis",  # Would come from ticket analysis
                "lat": ticket.get("loc_lat"),
                "lng": ticket.get("loc_lng"),
                "packet_id": packet_id,
                "order": ["image", "text", "pin"]
            },
            "status": "draft"
        }
        
        # Insert into database
        result = supabase.table("outbox_msgs").insert([outbox_msg]).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create outbox message")
        
        msg_id = result.data[0]["id"]
        
        # Audit dak_preview
        supabase.table("audit_log").insert({
            "actor": "system",
            "action": "dak_preview",
            "detail": {
                "ticket_id": ticket_id,
                "msg_id": msg_id,
                "packet_id": packet_id
            }
        }).execute()
        
        return DakPreviewOut(msg_id=msg_id)
        
    except HTTPException:
        raise
    except Exception as e:
        # Audit error
        if supabase:
            supabase.table("audit_log").insert({
                "actor": "system",
                "action": "dak_preview_error",
                "detail": {
                    "ticket_id": ticket_id,
                    "error": str(e)
                }
            }).execute()
        
        raise HTTPException(status_code=500, detail=f"DAK preview failed: {str(e)}")

@router.post("/approve/{msg_id}")
async def dak_approve(
    msg_id: str,
    authorization: str = Depends(verify_auth),
    x_supabase_role: str = Depends(verify_service_role),
):
    """
    Approve DAK message:
    - Set status to 'approved'
    - Set approved_by to auth.uid()
    - Audit 'dak_approved'
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not initialized")
    
    try:
        # Get current user ID from auth token (placeholder)
        # In real implementation, we'd extract user ID from JWT
        user_id = "00000000-0000-0000-0000-000000000000"  # Placeholder
        
        # Update outbox message
        result = supabase.table("outbox_msgs").update({
            "status": "approved",
            "approved_by": user_id
        }).eq("id", msg_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Outbox message not found")
        
        # Audit dak_approved
        supabase.table("audit_log").insert({
            "actor": "system",
            "action": "dak_approved",
            "detail": {
                "msg_id": msg_id,
                "approved_by": user_id
            }
        }).execute()
        
        return {"success": True, "msg_id": msg_id}
        
    except HTTPException:
        raise
    except Exception as e:
        # Audit error
        if supabase:
            supabase.table("audit_log").insert({
                "actor": "system",
                "action": "dak_approve_error",
                "detail": {
                    "msg_id": msg_id,
                    "error": str(e)
                }
            }).execute()
        
        raise HTTPException(status_code=500, detail=f"DAK approval failed: {str(e)}")