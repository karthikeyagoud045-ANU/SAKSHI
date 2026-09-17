"""
Analysis module for SAKSHI worker
Handles POST /analyze for text analysis, deduplication, LLM processing, and evidence linking
"""
import os
import json
import hashlib
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from worker.schemas import TextInput, AnalysisOut, FieldOutput
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

# Models would be imported from main app state
# For now, we'll placeholder the functionality

# Fallback rule templates (would be in fallbacks.py)
def rule_template_fallback(text: str) -> Dict[str, Any]:
    """Rule-based fallback when LLM is unavailable"""
    # Simple keyword-based classification
    text_lower = text.lower()
    
    # Category detection
    if any(word in text_lower for word in ["pothole", "road", "street", " pavement"]):
        category = "pothole"
    elif any(word in text_lower for word in ["garbage", "trash", "waste", "dump"]):
        category = "garbage"
    elif any(word in text_lower for word in ["light", "lamp", "electricity", "power"]):
        category = "streetlight"
    elif any(word in text_lower for word in ["water", "pipe", "leak", "flood"]):
        category = "water_supply"
    else:
        category = "other"
    
    # Urgency detection (simplified)
    urgency = "LOW"
    if any(word in text_lower for word in ["emergency", "danger", "accident", "fire", "flood"]):
        urgency = "HIGH"
    elif any(word in text_lower for word in ["urgent", "serious", "broken", "blocked"]):
        urgency = "MEDIUM"
    
    # Department mapping
    dept_map = {
        "pothole": "public_works",
        "garbage": "sanitation",
        "streetlight": "electrical",
        "water_supply": "water_dept",
        "other": "general"
    }
    dept = dept_map.get(category, "general")
    
    # Location (would be extracted from text or GPS in real implementation)
    location = {"lat": 0.0, "lng": 0.0}
    
    return {
        "category": category,
        "urgency": urgency,
        "dept": dept,
        "location": location,
        "missing": [] if location["lat"] != 0.0 else ["location"],
        "conflicts": [],
        "packet_draft": {
            "summary": text[:200],
            "category": category,
            "urgency": urgency
        }
    }

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two GPS coordinates in kilometers"""
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371.0  # Earth radius in km
    
    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)
    
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    return R * c

def geo_proximity(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Geo proximity score with decay ≤1 km"""
    distance_km = haversine_distance(lat1, lng1, lat2, lng2)
    if distance_km <= 1.0:
        return 1.0 - (distance_km / 1.0)  # Linear decay from 1.0 at 0km to 0.0 at 1km
    return 0.0

def time_window_score(hours_diff: float) -> float:
    """Time window score with decay ≤72 hours"""
    if hours_diff <= 72.0:
        return 1.0 - (hours_diff / 72.0)  # Linear decay from 1.0 at 0h to 0.0 at 72h
    return 0.0

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    if not vec1 or not vec2:
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm_vec1 = sum(a * a for a in vec1) ** 0.5
    norm_vec2 = sum(b * b for b in vec2) ** 0.5
    
    if norm_vec1 == 0 or norm_vec2 == 0:
        return 0.0
    
    return dot_product / (norm_vec1 * norm_vec2)

@router.post("/analyze", response_model=AnalysisOut)
async def analyze_ticket(input_data: TextInput):
    """
    Analyze a ticket:
    1. Run deduplication scoring against existing tickets
    2. Process text with LLM (wrapped in UNTRUSTED_DATA delimiters)
    3. Perform reflection pass for missing fields/conflicts
    4. Write claim_links for category/urgency/dept/location
    5. Return AnalysisOut
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not initialized")
    
    try:
        # Step 1: Get existing tickets for deduplication
        # Query tickets with status in (intake,triage,tray,human_review)
        existing_tickets_resp = supabase.table("tickets").select(
            "id, category, urgency, dept, loc_lat, loc_lng, loc_conf, created_at, status"
        ).in_("status", ["intake", "triage", "tray", "human_review"]).execute()
        
        existing_tickets = existing_tickets_resp.data or []
        
        # Step 2: Compute text embedding for input text
        # In real implementation, we'd use the sentence transformer model
        # For now, placeholder
        text_embedding = [0.1] * 384  # MiniLM embedding size
        
        # Step 3: Compute deduplication scores
        max_dup_score = 0.0
        best_parent_id = None
        dup_details = []
        
        for ticket in existing_tickets:
            # Text similarity (placeholder - would use actual ticket text embedding)
            text_sim = cosine_similarity(text_embedding, [0.1] * 384)  # Placeholder
            
            # Image similarity (placeholder)
            image_sim = 0.0
            if input_data.image_embed and ticket.get("loc_lat"):  # Simplified
                image_sim = cosine_similarity(input_data.image_embed, [0.2] * 384)  # Placeholder
            
            # Geo proximity
            geo_sim = 0.0
            if ticket.get("loc_lat") is not None and ticket.get("loc_lng") is not None:
                if input_data.gps:
                    geo_sim = geo_proximity(
                        input_data.gps["lat"], input_data.gps["lng"],
                        ticket["loc_lat"], ticket["loc_lng"]
                    )
            
            # Time window
            time_sim = 0.0
            if ticket.get("created_at"):
                from datetime import datetime
                try:
                    created_at = datetime.fromisoformat(ticket["created_at"].replace("Z", "+00:00"))
                    now = datetime.now()
                    hours_diff = abs((now - created_at).total_seconds()) / 3600
                    time_sim = time_window_score(hours_diff)
                except:
                    time_sim = 0.0
            
            # Calculate dup_score per formula
            dup_score = (
                0.35 * text_sim +
                0.25 * image_sim +
                0.25 * geo_sim +
                0.15 * time_sim
            )
            
            dup_details.append({
                "ticket_id": ticket["id"],
                "dup_score": dup_score,
                "text_sim": text_sim,
                "image_sim": image_sim,
                "geo_sim": geo_sim,
                "time_sim": time_sim
            })
            
            if dup_score > max_dup_score:
                max_dup_score = dup_score
                best_parent_id = ticket["id"]
        
        # Step 4: Apply deduplication bands
        new_status = input_data.ticket_id  # Keep existing status for now
        parent_id = None
        audit_action = None
        
        # Get current ticket status (in real implementation, we'd fetch it)
        current_status = "intake"  # Placeholder
        
        # Check if HIGH urgency on either ticket would suspend auto-link
        current_urgency = "MEDIUM"  # Placeholder - would come from LLM/fallback
        parent_has_high_urgency = False  # Would check parent ticket
        
        high_urgency_override = (current_urgency == "HIGH" or parent_has_high_urgency)
        
        if max_dup_score > 0.85 and not high_dup_override:
            # Auto-link to duplicate
            status = "tray"
            parent_id = best_parent_id
            audit_action = "dup_linked"
        elif max_dup_score > 0.60:
            # Flagged for review
            status = current_status  # Keep current status
            parent_id = None
            audit_action = "dup_flagged"
        else:
            # No significant duplicate
            status = current_status
            parent_id = None
            audit_action = None
        
        # Step 5: LLM processing (with UNTRUSTED_DATA delimiter)
        # In real implementation:
        # - Wrap text in ---UNTRUSTED_DATA---\n{text}\n---END_UNTRUSTED_DATA---
        # - Call LLM with structured output (temperature 0)
        # - Validate with pydantic
        # - On validation failure, use fallbacks.rule_template()
        
        # For now, use fallback directly
        llm_result = rule_template_fallback(input_data.text)
        
        # Override with computed values where appropriate
        category = llm_result["category"]
        urgency = llm_result["urgency"]
        dept = llm_result["dept"]
        location_val = llm_result["location"]
        missing = llm_result["missing"]
        conflicts = llm_result["conflicts"]
        packet_draft = llm_result["packet_draft"]
        
        # Step 6: Reflection pass
        # Checklist: location present? conf≥0.6? category conf? photo quality? text-vs-image conflict?
        # For now, simplified
        if input_data.gps is None:
            if "location" not in missing:
                missing.append("location")
        
        # If urgency is HIGH or missing contains 'location', status -> human_review
        if urgency == "HIGH" or "location" in missing:
            status = "human_review"
        
        # Step 7: Write claim_links
        # In real implementation, we'd create claim_links for:
        # - category -> transcript evidence
        # - urgency -> transcript evidence
        # - dept -> transcript evidence
        # - location -> transcript evidence or gps evidence
        
        # Step 8: Audit the analysis
        if supabase:
            supabase.table("audit_log").insert({
                "actor": "system",
                "action": "analyze",
                "detail": {
                    "ticket_id": input_data.ticket_id,
                    "dup_score": max_dup_score,
                    "parent_id": parent_id,
                    "category": category,
                    "urgency": urgency,
                    "dept": dept,
                    "missing": missing,
                    "conflicts": conflicts
                }
            }).execute()
        
        # Step 9: Prepare response
        # Get evidence IDs for linking (placeholder)
        transcript_evidence_id = "transcript-evidence-id-placeholder"
        gps_evidence_id = "gps-evidence-id-placeholder" if input_data.gps else None
        
        evidence_refs = []
        if transcript_evidence_id:
            evidence_refs.append(transcript_evidence_id)
        if gps_evidence_id:
            evidence_refs.append(gps_evidence_id)
        
        return AnalysisOut(
            category=FieldOutput(
                value=category,
                confidence=0.8,  # Placeholder
                evidence=evidence_refs
            ),
            urgency=FieldOutput(
                value=urgency,
                confidence=0.8,  # Placeholder
                evidence=evidence_refs
            ),
            department=FieldOutput(
                value=dept,
                confidence=0.8,  # Placeholder
                evidence=evidence_refs
            ),
            location=FieldOutput(
                value=location_val,
                confidence=0.8 if input_data.gps else 0.0,  # Placeholder
                evidence=[gps_evidence_id] if gps_evidence_id else []
            ),
            missing=missing,
            conflicts=conflicts,
            dup_score=max_dup_score,
            parent_id=parent_id,
            status=status,
            packet_draft=packet_draft
        )
        
    except Exception as e:
        # Audit error
        if supabase:
            supabase.table("audit_log").insert({
                "actor": "system",
                "action": "analyze_error",
                "detail": {
                    "ticket_id": input_data.ticket_id,
                    "error": str(e)
                }
            }).execute()
        
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")