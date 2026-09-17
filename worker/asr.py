"""ASR websocket with an explicit deterministic offline stub."""
import hashlib
import os
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from worker.store import get_store

router = APIRouter()

@router.websocket("/asr")
async def asr_endpoint(websocket: WebSocket):
    await websocket.accept(); audio = bytearray(); mode = os.getenv("ASR_MODE", "stub")
    try:
        while True:
            chunk = await websocket.receive_bytes(); audio.extend(chunk)
            if mode == "stub":
                text = os.getenv("ASR_STUB_TEXT", "offline stub transcript")
                await websocket.send_json({"type": "partial", "text": text, "mode": "stub"})
                digest = hashlib.sha256(audio).hexdigest()
                try:
                    get_store().put_original(f"audio/{digest}.pcm", bytes(audio))
                except FileExistsError:
                    pass
                get_store().audit("asr_stub", {"audio_sha256": digest})
                await websocket.send_json({"type": "final", "text": text, "spans": [{"start_s": 0.0, "end_s": len(audio) / 32000, "text": text}], "language": "stub", "mode": "stub"})
                audio.clear()
            else:
                raise RuntimeError("real ASR dependencies are unavailable in offline mode")
    except (WebSocketDisconnect, RuntimeError):
        if mode != "stub":
            await websocket.send_json({"type": "fallback", "fallback": "web_speech"})
    finally:
        await websocket.close()
