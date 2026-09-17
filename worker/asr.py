"""
ASR (Automatic Speech Recognition) module for SAKSHI worker
Handles WebSocket /ws/asr endpoint for streaming audio processing
"""
import asyncio
import json
import hashlib
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from worker.schemas import AsrPartial, AsrFinal, AsrFallback
import os
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

# VAD and Whisper models would be imported from main app state
# For now, we'll placeholder them

@router.websocket("/asr")
async def asr_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Get models from app state (in real implementation, these would be passed)
    # For now, we'll simulate
    
    audio_buffer = bytearray()
    is_speaking = False
    silence_counter = 0
    SILENCE_THRESHOLD = int(os.getenv("VAD_SILENCE_MS", "600")) // 50  # Assuming 50ms chunks
    
    try:
        while True:
            # Receive binary audio chunk (PCM16 16kHz)
            data = await websocket.receive_bytes()
            audio_buffer.extend(data)
            
            # In a real implementation, we'd run VAD on the chunk
            # For now, simulate voice activity detection
            has_voice = len(data) > 0  # Placeholder
            
            if has_voice:
                is_speaking = True
                silence_counter = 0
                
                # If we have enough audio (2-4 seconds), process for partial
                if len(audio_buffer) >= 16000 * 2 * 2:  # 2 seconds of 16kHz PCM16
                    # Run faster-whisper on chunk (placeholder)
                    partial_text = "partial transcript"  # Placeholder
                    
                    # Send partial result
                    partial = AsrPartial(text=partial_text)
                    await websocket.send_text(partial.json())
                    
                    # Keep some overlap for continuity
                    if len(audio_buffer) > 16000 * 4 * 2:  # More than 4 seconds
                        audio_buffer = audio_buffer[16000 * 2 * 2:]  # Keep last 2 seconds
            else:
                silence_counter += 1
                if is_speaking and silence_counter >= SILENCE_THRESHOLD:
                    # End of speech detected
                    is_speaking = False
                    
                    if len(audio_buffer) > 0:
                        # Process final transcription
                        final_text = "final transcript of the complaint"  # Placeholder
                        language = "en"  # Placeholder
                        
                        # Create spans (placeholder)
                        spans = [{"start_s": 0.0, "end_s": 3.0, "text": final_text}]
                        
                        # Send final result
                        final = AsrFinal(
                            text=final_text,
                            spans=spans,
                            language=language
                        )
                        await websocket.send_text(final.json())
                        
                        # Persist audio to storage (placeholder)
                        # In real implementation:
                        # 1. Compute SHA256 of audio_buffer
                        # 2. Upload to originals bucket via service role
                        # 3. Create evidence record for kind='audio'
                        # 4. Create evidence record for kind='transcript'
                        # 5. Audit 'asr_final'
                        
                        # Reset buffer
                        audio_buffer = bytearray()
                    else:
                        # No audio sent, just send empty final
                        final = AsrFinal(text="", spans=[], language="")
                        await websocket.send_text(final.json())
                
                elif silence_counter > SILENCE_THRESHOLD * 2:  # Extended silence
                    # Reset if too much silence
                    is_speaking = False
                    audio_buffer = bytearray()
                    
    except WebSocketDisconnect:
        print("Client disconnected from ASR WebSocket")
    except Exception as e:
        print(f"Error in ASR WebSocket: {e}")
        try:
            # Send fallback if worker ASR unavailable
            fallback = AsrFallback()
            await websocket.send_text(fallback.json())
        except:
            pass  # Ignore errors on fallback
    finally:
        await websocket.close()