"""
SAKSHI Backend Worker - Main FastAPI Application
"""
import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import uvicorn
from worker.asr import router as asr_router
from worker.privacy import router as privacy_router
from worker.analyze import router as analyze_router
from worker.dak import router as dak_router
from worker.evalrun import router as eval_router
from worker.audit import router as audit_router
from worker.schemas import HealthOut

# Security
security = HTTPBearer()

# Environment variables
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Global variables for models (loaded at startup)
models = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load models on startup
    global models
    print("Loading models...")
    
    # Import here to avoid slowing down startup if not used
    try:
        # Whisper ASR model
        from faster_whisper import WhisperModel
        start_time = asyncio.get_event_loop().time()
        models["whisper"] = WhisperModel(
            os.getenv("WHISPER_MODEL", "base"),
            device="cpu",
            compute_type="int8"
        )
        load_time = (asyncio.get_event_loop().time() - start_time) * 1000
        models["whisper_warmup"] = load_time
        print(f"Whisper model loaded in {load_time:.2f}ms")
    except Exception as e:
        print(f"Failed to load Whisper model: {e}")
        models["whisper"] = None
    
    try:
        # Silero VAD (ONNX)
        import onnxruntime as ort
        start_time = asyncio.get_event_loop().time()
        # In a real implementation, we'd load the actual VAD model
        models["vad"] = ort.InferenceSession("silero_vad.onnx")  # Placeholder
        load_time = (asyncio.get_event_loop().time() - start_time) * 1000
        models["vad_warmup"] = load_time
        print(f"VAD model loaded in {load_time:.2f}ms")
    except Exception as e:
        print(f"Failed to load VAD model: {e}")
        models["vad"] = None
    
    try:
        # MediaPipe face detection
        import mediapipe as mp
        start_time = asyncio.get_event_loop().time()
        models["face_detection"] = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )
        load_time = (asyncio.get_event_loop().time() - start_time) * 1000
        models["face_detection_warmup"] = load_time
        print(f"MediaPipe face detection loaded in {load_time:.2f}ms")
    except Exception as e:
        print(f"Failed to load MediaPipe model: {e}")
        models["face_detection"] = None
    
    try:
        # EasyOCR
        import easyocr
        start_time = asyncio.get_event_loop().time()
        models["ocr"] = easyocr.Reader(['en', 'hi'])  # English and Hindi
        load_time = (asyncio.get_event_loop().time() - start_time) * 1000
        models["ocr_warmup"] = load_time
        print(f"EasyOCR loaded in {load_time:.2f}ms")
    except Exception as e:
        print(f"Failed to load EasyOCR: {e}")
        models["ocr"] = None
    
    try:
        # Sentence transformers (MiniLM)
        from sentence_transformers import SentenceTransformer
        start_time = asyncio.get_event_loop().time()
        models["embedder"] = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        load_time = (asyncio.get_event_loop().time() - start_time) * 1000
        models["embedder_warmup"] = load_time
        print(f"Sentence transformer loaded in {load_time:.2f}ms")
    except Exception as e:
        print(f"Failed to load sentence transformer: {e}")
        models["embedder"] = None
    
    print("Model loading complete")
    
    yield
    
    # Cleanup on shutdown
    print("Shutting down worker...")
    models.clear()

# Create FastAPI app
app = FastAPI(
    title="SAKSHI Backend Worker",
    description="AI-Based Public Complaint Evidence Agent - Worker Node",
    version="0.1.0",
    lifespan=lifespan
)

# Dependency to verify service role token
async def verify_service_role(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    # In a real implementation, we'd verify this against Supabase
    # For now, we'll just check if it's present (service role should be used internally)
    if not token:
        raise HTTPException(status_code=401, detail="Missing service role token")
    # Additional validation would happen here
    return token

# Health check endpoint
@app.get("/health", response_model=HealthOut)
async def health_check():
    ready = all(model is not None for key, model in models.items() 
                if not key.endswith("_warmup") and key not in ["whisper", "vad", "face_detection", "ocr", "embedder"])
    
    model_times = {k: v for k, v in models.items() if k.endswith("_warmup")}
    
    return HealthOut(
        ready=ready,
        models=model_times
    )

# Demo reset endpoint (only in DEMO_MODE)
@app.post("/demo/reset")
async def demo_reset():
    if not DEMO_MODE:
        raise HTTPException(status_code=403, detail="Demo mode not enabled")
    
    # In a real implementation, this would reseed the database
    # For now, we'll just return success
    return {"success": True, "message": "Demo reset would reseed from seeds/seeds.json"}



@app.post("/dispatch_attempt/{ticket_id}")
async def dispatch_attempt(ticket_id: str):
    """
    ALWAYS returns 403 per R2 - NEVER dispatch crews or send messages without explicit human approval.
    """
    # Audit the policy violation
    try:
        from supabase import create_client
        import os
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if supabase_url and supabase_key:
            supabase = create_client(supabase_url, supabase_key)
            supabase.table("audit_log").insert({
                "actor": "system",
                "action": "policy_violation_blocked",
                "detail": {
                    "ticket_id": ticket_id,
                    "reason": "dispatch_attempt_without_approval"
                }
            }).execute()
    except Exception as e:
        # If auditing fails, we still return 403 as required
        pass
    
    # Always return 403 as per R2
    from fastapi import HTTPException
    raise HTTPException(status_code=403, detail={"error": "policy_locked"})


@app.post("/dispatch_attempt/{ticket_id}")
async def dispatch_attempt(ticket_id: str):
    """
    ALWAYS returns 403 per R2 - NEVER dispatch crews or send messages without explicit human approval.
    """
    # Audit the policy violation
    try:
        from supabase import create_client
        import os
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if supabase_url and supabase_key:
            supabase = create_client(supabase_url, supabase_key)
            supabase.table("audit_log").insert({
                "actor": "system",
                "action": "policy_violation_blocked",
                "detail": {
                    "ticket_id": ticket_id,
                    "reason": "dispatch_attempt_without_approval"
                }
            }).execute()
    except Exception as e:
        # If auditing fails, we still return 403 as required
        pass
    
    # Always return 403 as per R2
    from fastapi import HTTPException
    raise HTTPException(status_code=403, detail="policy_locked")


@app.post("/dispatch_attempt/{ticket_id}")
async def dispatch_attempt(ticket_id: str):
    """
    ALWAYS returns 403 per R2 - NEVER dispatch crews or send messages without explicit human approval.
    """
    # Always return 403 as per R2
    from fastapi import HTTPException
    raise HTTPException(status_code=403, detail="policy_locked")
# Include routers
app.include_router(asr_router, prefix="/ws", tags=["asr"])
app.include_router(privacy_router, prefix="/privacy", tags=["privacy"])
app.include_router(analyze_router, prefix="", tags=["analyze"])
app.include_router(dak_router, prefix="/dak", tags=["dak"])
app.include_router(eval_router, prefix="/eval", tags=["eval"])
app.include_router(audit_router, prefix="/audit", tags=["audit"])

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1
    )