"""
Pydantic schemas for SAKSHI worker
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

# Input schemas
class TextInput(BaseModel):
    ticket_id: str
    text: str
    language: str = "auto"
    spans: List[Dict[str, Any]] = []
    gps: Optional[Dict[str, float]] = None  # {"lat": float, "lng": float}
    image_embed: Optional[List[float]] = None

# Output schemas for /analyze endpoint
class FieldOutput(BaseModel):
    value: Any
    confidence: float
    evidence: List[str] = []  # evidence IDs

class AnalysisOut(BaseModel):
    category: FieldOutput
    urgency: FieldOutput
    department: FieldOutput
    location: FieldOutput
    missing: List[str] = []
    conflicts: List[Any] = []
    dup_score: float
    parent_id: Optional[str] = None
    status: str  # intake|triage|tray|merged|human_review|approved|sent
    packet_draft: Dict[str, Any] = {}

# WebSocket ASR output schemas
class AsrPartial(BaseModel):
    type: str = "partial"
    text: str

class AsrFinal(BaseModel):
    type: str = "final"
    text: str
    spans: List[Dict[str, float]]  # [{"start_s": float, "end_s": float, "text": str}]
    language: str

class AsrFallback(BaseModel):
    type: str = "fallback"
    fallback: str = "web_speech"

# DAK preview schemas
class DakPreviewOut(BaseModel):
    msg_id: str

# Health check schema
class HealthOut(BaseModel):
    ready: bool
    models: Dict[str, float]  # {model_name: warmup_time_ms}

# Audit log entry
class AuditEntry(BaseModel):
    actor: str
    action: str
    detail: Dict[str, Any] = {}

# Evaluation metrics
class EvalMetrics(BaseModel):
    task_completion: float
    dup_precision: float
    dup_recall: float
    urgency_agreement: float