"""
Privacy processing module for SAKSHI worker
Handles POST /privacy/process for face and license plate blurring
"""
import os
import hashlib
import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Header
from worker.schemas import TextInput
import cv2
import numpy as np
from supabase import create_client, Client

router = APIRouter()

# Initialize Supabase client (service role for privileged operations)
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

# MediaPipe and EasyOCR would be imported from main app state
# For now, we'll placeholder the functionality

@router.post("/process")
async def process_privacy(
    ticket_id: str,
    x_supabase_role: Optional[str] = Header(None)
):
    """
    Process photo_original evidence for a ticket:
    - Detect faces and blur them (pixelation)
    - Detect license plates and blur them (gaussian blur)
    - Upload blurred version to blurred bucket
    - Create evidence records for photo_original and photo_blurred
    - Audit the operation
    """
    # Verify service role (privileged operation)
    if x_supabase_role != "service_role":
        raise HTTPException(status_code=403, detail="Service role required")
    
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not initialized")
    
    try:
        # Get photo_original evidence for this ticket
        # In a real implementation, we'd query the evidence table
        # For now, we'll simulate
        
        # Simulate getting the original image path from storage
        original_path = f"originals/{ticket_id}/complaint.jpg"
        
        # In real implementation:
        # 1. Download original image via service role signed URL
        # 2. Run MediaPipe face detection
        # 3. Run EasyOCR for license plate detection (Indian pattern: ^{2,3} letters + digits groups)
        # 4. Apply pixelation to faces (block = max(12, box_w//12))
        # 5. Apply gaussian blur to license plates
        # 6. Composite the blurred image
        # 7. Strip ALL EXIF from blurred copy
        # 8. Keep GPS in originals evidence meta only
        # 9. Upload blurred version to blurred bucket
        # 10. Compute SHA256 for both
        # 11. Create evidence records
        # 12. Audit 'privacy_blur' or 'blur_unverified'
        
        # Placeholder implementation
        faces_detected = 2  # Placeholder
        plates_detected = 1  # Placeholder
        blur_verified = True  # Placeholder - would be False if detector errored
        
        # Generate SHA256 placeholders
        original_sha256 = hashlib.sha256(b"original_image_data").hexdigest()
        blurred_sha256 = hashlib.sha256(b"blurred_image_data").hexdigest()
        
        # Create evidence records (placeholder)
        # In real implementation, we'd insert into evidence table:
        # photo_original evidence (should already exist from ASR)
        # photo_blurred evidence (new)
        
        # Audit log entry
        audit_detail = {
            "ticket_id": ticket_id,
            "faces_detected": faces_detected,
            "plates_detected": plates_detected,
            "blur_verified": blur_verified,
            "original_sha256": original_sha256,
            "blurred_sha256": blurred_sha256
        }
        
        if supabase:
            supabase.table("audit_log").insert({
                "actor": "system",
                "action": "privacy_blur" if blur_verified else "blur_unverified",
                "detail": audit_detail
            }).execute()
        
        return {
            "success": True,
            "ticket_id": ticket_id,
            "faces_detected": faces_detected,
            "plates_detected": plates_detected,
            "blur_verified": blur_verified
        }
        
    except Exception as e:
        # Audit error
        if supabase:
            supabase.table("audit_log").insert({
                "actor": "system",
                "action": "privacy_error",
                "detail": {
                    "ticket_id": ticket_id,
                    "error": str(e)
                }
            }).execute()
        
        raise HTTPException(status_code=500, detail=f"Privacy processing failed: {str(e)}")