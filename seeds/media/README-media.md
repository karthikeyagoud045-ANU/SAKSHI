# Media Assets for SAKSHI Verification

This directory should contain media assets used for end-to-end verification.

## Required Files

### voice_001.wav
- A 10-second audio complaint in PCM16 format, 16kHz sample rate
- Language: Hindi or Telugu (to test multilingual capabilities)
- Content: Example complaint (e.g., "There is a pothole on Main Street causing traffic delays")
- Format: WAV, PCM16, 16kHz, mono

### photo_001.jpg
- A photo containing at least one human face (to test face detection and blurring)
- Should also ideally contain a license plate or text to test OCR (optional)
- Format: JPG

## How to Create These Files

### For voice_001.wav:
1. Record a 10-second complaint in Hindi or Telugu using your smartphone
2. Convert to PCM16 WAV format at 16kHz:
   ```bash
   ffmpeg -i input.m4a -ar 16000 -ac 1 -sample_fmt s16 voice_001.wav
   ```

### For photo_001.jpg:
1. Take a photo that includes a clear human face
2. Ensure you have consent if it's a photo of a real person
3. Save as JPG format

## Verification Script Behavior

The `scripts/verify.sh` script will:
- Check for these files in `seeds/media/`
- If present: use them for end-to-end testing
- If absent: skip those verification steps with a warning (marking as 'PENDING-MEDIA')
