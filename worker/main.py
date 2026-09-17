"""Offline-safe SAKSHI worker entrypoint."""
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from worker.asr import router as asr_router
from worker.privacy import router as privacy_router
from worker.analyze import router as analyze_router
from worker.dak import router as dak_router
from worker.evalrun import router as eval_router
from worker.audit import router as audit_router
from worker.store import get_store

app = FastAPI(title="SAKSHI Backend Worker", version="0.1.0")

@app.get("/health")
async def health_check():
    return {"ready": True, "models": {"asr": os.getenv("ASR_MODE", "stub"), "storage": os.getenv("STORAGE_MODE", "local")}}

@app.post("/demo/reset")
async def demo_reset():
    if os.getenv("DEMO_MODE", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Demo mode not enabled")
    get_store().data["tickets"].clear()
    get_store().audit("demo_reset", {"mode": "local"})
    return {"success": True}

@app.post("/dispatch_attempt/{ticket_id}")
async def dispatch_attempt(ticket_id: str):
    get_store().audit("policy_violation_blocked", {"ticket_id": ticket_id})
    return JSONResponse(status_code=403, content={"error": "policy_locked"})

app.include_router(asr_router, prefix="/ws", tags=["asr"])
app.include_router(privacy_router, prefix="/privacy", tags=["privacy"])
app.include_router(analyze_router, tags=["analyze"])
app.include_router(dak_router, prefix="/dak", tags=["dak"])
app.include_router(eval_router, prefix="/eval", tags=["eval"])
app.include_router(audit_router, prefix="/audit", tags=["audit"])
