#!/usr/bin/env python3
"""
WebSocket client for testing SAKSHI ASR endpoint
Streams audio file in 2-second PCM16 chunks to /ws/asr
"""
import asyncio
import json
import time
import wave
import sys
import os

# Add worker directory to path for imports if needed
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'worker'))

import websockets

async def test_asr(ws_url, audio_file_path):
    """Test ASR WebSocket endpoint with audio file"""
    
    # Check if audio file exists
    if not os.path.exists(audio_file_path):
        print(f"Error: Audio file not found: {audio_file_path}")
        return False
    
    # Open and read WAV file
    try:
        with wave.open(audio_file_path, 'rb') as wav_file:
            # Check format
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            framerate = wav_file.getframerate()
            n_frames = wav_file.getnframes()
            
            print(f"Audio file info:")
            print(f"  Channels: {channels}")
            print(f"  Sample width: {sample_width} bytes")
            print(f"  Frame rate: {framerate} Hz")
            print(f"  Frames: {n_frames}")
            print(f"  Duration: {n_frames / framerate:.2f} seconds")
            
            # Validate format (expecting PCM16, 16kHz, mono)
            if channels != 1:
                print(f"Warning: Expected mono (1 channel), got {channels} channels")
            if sample_width != 2:
                print(f"Error: Expected 16-bit (2 bytes) sample width, got {sample_width}")
                return False
            if framerate != 16000:
                print(f"Warning: Expected 16000 Hz, got {framerate} Hz")
            
            # Read all audio data
            audio_data = wav_file.readframes(n_frames)
            
    except Exception as e:
        print(f"Error reading WAV file: {e}")
        return False
    
    # Calculate chunk size (2 seconds of audio)
    bytes_per_second = framerate * channels * sample_width
    chunk_size = bytes_per_second * 2  # 2 seconds
    
    print(f"\nStreaming audio in {chunk_size}-byte chunks (~2 seconds each)...")
    
    try:
        # Connect to WebSocket
        async with websockets.connect(ws_url) as websocket:
            print(f"Connected to {ws_url}")
            
            # Stream audio chunks
            offset = 0
            chunk_num = 0
            start_time = time.time()
            
            while offset < len(audio_data):
                # Extract chunk
                chunk = audio_data[offset:offset + chunk_size]
                if len(chunk) == 0:
                    break
                
                # Send chunk
                chunk_start_time = time.time()
                await websocket.send(chunk)
                
                # Wait for response (with timeout)
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    response_time = time.time()
                    
                    # Parse and print response
                    try:
                        data = json.loads(response)
                        timestamp = response_time - start_time
                        
                        if data.get('type') == 'partial':
                            print(f"[{timestamp:.3f}s] PARTIAL: {data.get('text', '')}")
                        elif data.get('type') == 'final':
                            print(f"[{timestamp:.3f}s] FINAL: {data.get('text', '')}")
                            print(f"  Language: {data.get('language', 'unknown')}")
                            print(f"  Spans: {data.get('spans', [])}")
                        elif data.get('type') == 'fallback':
                            print(f"[{timestamp:.3f}s] FALLBACK: {data.get('fallback', '')}")
                        else:
                            print(f"[{timestamp:.3f}s] UNKNOWN: {data}")
                            
                    except json.JSONDecodeError:
                        print(f"[{response_time - start_time:.3f}s] RAW: {response}")
                        
                except asyncio.TimeoutError:
                    print(f"[{time.time() - start_time:.3f}s] WARNING: No response received (timeout)")
                
                # Move to next chunk
                offset += len(chunk)
                chunk_num += 1
                
                # Small delay to simulate real-time streaming
                # (optional, removes this for faster testing)
                # await asyncio.sleep(0.1)
            
            # Send empty chunk to signal end of stream? Or just wait for final
            # Actually, we should wait a bit for final processing
            print("\nWaiting for final processing...")
            try:
                # Wait for any remaining responses
                while True:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    response_time = time.time()
                    try:
                        data = json.loads(response)
                        timestamp = response_time - start_time
                        
                        if data.get('type') == 'partial':
                            print(f"[{timestamp:.3f}s] PARTIAL: {data.get('text', '')}")
                        elif data.get('type') == 'final':
                            print(f"[{timestamp:.3f}s] FINAL: {data.get('text', '')}")
                            print(f"  Language: {data.get('language', 'unknown')}")
                            print(f"  Spans: {data.get('spans', [])}")
                        elif data.get('type') == 'fallback':
                            print(f"[{timestamp:.3f}s] FALLBACK: {data.get('fallback', '')}")
                        else:
                            print(f"[{timestamp:.3f}s] UNKNOWN: {data}")
                    except json.JSONDecodeError:
                        print(f"[{response_time - start_time:.3f}s] RAW: {response}")
            except asyncio.TimeoutError:
                print(f"[{time.time() - start_time:.3f}s] No more responses (timeout)")
            
            total_time = time.time() - start_time
            print(f"\nStreaming complete. Total time: {total_time:.3f}s")
            return True
            
    except Exception as e:
        print(f"WebSocket error: {e}")
        return False

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test SAKSHI ASR WebSocket endpoint')
    parser.add_argument('--url', default='ws://localhost:8000/ws/asr',
                        help='WebSocket URL (default: ws://localhost:8000/ws/asr)')
    parser.add_argument('--audio', default='seeds/media/voice_001.wav',
                        help='Path to audio file (default: seeds/media/voice_001.wav)')
    
    args = parser.parse_args()
    
    # Convert relative path to absolute if needed
    if not os.path.isabs(args.audio):
        args.audio = os.path.join(os.path.dirname(__file__), '..', args.audio)
    
    print(f"SAKSHI ASR WebSocket Client")
    print(f"WebSocket URL: {args.url}")
    print(f"Audio file: {args.audio}")
    print("-" * 50)
    
    # Run the test
    success = asyncio.run(test_asr(args.url, args.audio))
    
    if success:
        print("\n✓ ASR test completed successfully")
        sys.exit(0)
    else:
        print("\n✗ ASR test failed")
        sys.exit(1)

if __name__ == '__main__':
    main()
