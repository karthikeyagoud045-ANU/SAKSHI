"""
Audit module for SAKSHI worker
Handles audit log queries and management
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from worker.schemas import AuditEntry
from supabase import create_client, Client
import os

router = APIRouter()

# Initialize Supabase client
supabase: Client = None

def init_supabase():
    global supabase
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")  # Use anon key for audited reads
    if supabase_url and supabase_key:
        supabase = create_client(supabase_url, supabase_key)
    else:
        raise ValueError("Supabase URL and anon key must be set")

# Initialize on module load
try:
    init_supabase()
except Exception as e:
    print(f"Warning: Could not initialize Supabase client: {e}")

# Security dependency
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
security = HTTPBearer()

async def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify authenticated user"""
    token = credentials.credentials
    # In real implementation, verify token against Supabase auth
    # For now, just check if present
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    return token

@router.get("/tickets/{ticket_id}")
async def get_ticket_audit(
    ticket_id: str,
    authorization: str = Depends(verify_auth)
):
    """Get audit log entries for a specific ticket"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not initialized")
    
    try:
        # Query audit log for actions related to this ticket
        # In real implementation, we'd filter by detail containing ticket_id
        # For now, we'll get recent entries
        result = supabase.table("audit_log").select(
            "id, ts, actor, action, detail"
        ).order("ts", desc=True).limit(100).execute()
        
        # Filter for ticket-related entries (simplified)
        ticket_audit = []
        for entry in result.data or []:
            detail = entry.get("detail", {})
            if detail.get("ticket_id") == ticket_id or "ticket_id" in str(detail):
                ticket_audit.append(entry)
        
        return ticket_audit
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch audit log: {str(e)}")

@router.get("/recent")
async def get_recent_audit(
    limit: int = 50,
    authorization: str = Depends(verify_auth)
):
    """Get recent audit log entries"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not initialized")
    
    try:
        result = supabase.table("audit_log").select(
            "id, ts, actor, action, detail"
        ).order("ts", desc=True).limit(limit).execute()
        
        return result.data or []
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch recent audit: {str(e)}")

@router.get("/stats")
async def get_audit_stats(
    authorization: str = Depends(verify_auth)
):
    """Get audit log statistics"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not initialized")
    
    try:
        # Get counts by action type
        result = supabase.table("audit_log").select("action").execute()
        
        actions = [row["action"] for row in result.data or []]
        stats = {}
        for action in actions:
            stats[action] = stats.get(action, 0) + 1
        
        return {
            "total_entries": len(actions),
            "actions": stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch audit stats: {str(e)}")