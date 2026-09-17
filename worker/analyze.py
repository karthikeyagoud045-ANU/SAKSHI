"""Contract-safe complaint analysis with an offline rule fallback."""
import json
from math import atan2, cos, radians, sin, sqrt
from fastapi import APIRouter
from worker import llm_pool
from worker.fallbacks import rule_template_fallback
from worker.schemas import AnalysisOut, FieldOutput, TextInput
from worker.store import get_store

router = APIRouter()

def haversine_distance(lat1, lon1, lat2, lon2):
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * atan2(sqrt(a), sqrt(1 - a))

def geo_proximity(lat1, lng1, lat2, lng2):
    return max(0.0, 1.0 - haversine_distance(lat1, lng1, lat2, lng2))

def time_window_score(hours_diff):
    return max(0.0, 1.0 - hours_diff / 72.0)

def cosine_similarity(vec1, vec2):
    if not vec1 or not vec2:
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm = sqrt(sum(a * a for a in vec1) * sum(b * b for b in vec2))
    return dot / norm if norm else 0.0

def _analysis(text):
    messages = [{"role": "system", "content": "Return only JSON."}, {"role": "user", "content": f"---UNTRUSTED_DATA---\n{text}\n---END_UNTRUSTED_DATA---"}]
    try:
        result = json.loads(llm_pool.chat_json(messages))
        if not {"category", "urgency", "dept", "location", "missing", "conflicts", "packet_draft"} <= result.keys():
            raise ValueError("invalid LLM schema")
        return result, False
    except Exception:
        return rule_template_fallback(text), True

@router.post("/analyze", response_model=AnalysisOut)
async def analyze_ticket(input_data: TextInput):
    result, fallback = _analysis(input_data.text)
    if fallback:
        get_store().audit("analyze_fallback", {"ticket_id": input_data.ticket_id, "reason": "llm_unavailable"})
    missing = list(result["missing"])
    if input_data.gps is None and "location" not in missing:
        missing.append("location")
    status = "human_review" if result["urgency"] == "HIGH" or "location" in missing else "triage"
    confidence = 0.0 if fallback else 0.8
    return AnalysisOut(category=FieldOutput(value=result["category"], confidence=confidence, evidence=[]), urgency=FieldOutput(value=result["urgency"], confidence=confidence, evidence=[]), department=FieldOutput(value=result["dept"], confidence=confidence, evidence=[]), location=FieldOutput(value=input_data.gps or result["location"], confidence=confidence if input_data.gps else 0.0, evidence=[]), missing=missing, conflicts=result["conflicts"], dup_score=0.0, parent_id=None, status=status, packet_draft={**result["packet_draft"], "badge": "UNCERTAIN" if fallback else "AI-DRAFT"})
