# SAKSHI Backend Worker

AI-Based Public Complaint Evidence Agent - Backend Core Worker

## Overview
This is the backend worker for the SAKSHI project, an AI-Based Public Complaint Evidence Agent for hackathon problem statement AIA33. The worker handles:
- Streaming ASR (Automatic Speech Recognition) for audio complaints
- Privacy processing (face/license plate blurring)
- Text analysis, categorization, urgency detection, and deduplication
- DAK (Direct Agent Komunikasi) message preparation and sending
- Evaluation runner for testing
- Audit logging
- All operations comply with strict privacy and security constraints (R1-R8)

## Architecture
- **Language**: Python 3.11
- **Framework**: FastAPI
- **Database**: Supabase Postgres
- **Storage**: Supabase Storage (3 private buckets: originals, blurred, outbox)
- **ASR**: faster-wisper int8 + Silero VAD (ONNX)
- **Privacy**: MediaPipe face detection, EasyOCR
- **NLP**: Sentence-transformers (MiniLM)
- **LLM**: Structured output with temperature 0
- **Realtime**: Supabase Realtime

## Setup

### Prerequisites
- Python 3.11+
- Supabase account and project
- Git

### Installation
1. Clone the repository
2. Copy `.env.example` to `.env` and fill in your Supabase and LLM credentials
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up Supabase:
   - Apply the migration: `supabase/migrations/001_init.sql`
   - Create the 3 private storage buckets: `originals`, `blurred`, `outbox`
   - Enable Realtime for tables: `tickets`, `audit_log`, `outbox_msgs`

### Environment Variables
See `.env.example` for required variables:
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_ANON_KEY`: Supabase anon key
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role key (for privileged operations)
- `LLM_API_KEY`: API key for your LLM provider
- `LLM_MODEL`: LLM model identifier (e.g., `gpt-4`, `claude-3-sonnet`)
- `WHISPER_MODEL`: Whisper model size (`tiny`, `base`, `small`, `medium`, `large`)
- `VAD_SILENCE_MS`: Voice activity detection silence threshold in milliseconds (default: 600)
- `DEMO_MODE`: Set to `true` to enable demo reset endpoint
- `WA_MODE`: WhatsApp mode (`simulator` or `cloud_test`)
- `WHATSAPP_TOKEN`: Required if `WA_MODE=cloud_test`

## Running the Worker

### Development
```bash
uvicorn worker.main:app --reload --host 0.0.0.0 --port 8000
```

### Production
```bash
uvicorn worker.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Endpoints

### Health Check
- `GET /health` - Returns worker readiness and model warmup times

### Demo (Development Only)
- `POST /demo/reset` - Reseeds database from seeds/seeds.json (only if DEMO_MODE=true)

### ASR (WebSocket)
- `WS /ws/asr` - Streaming audio processing
  - Accepts: Binary PCM16 16kHz chunks (2-4 second segments)
  - Returns: JSON messages:
    - `{type: 'partial', text}` per chunk
    - `{type: 'final', text, spans:[{start_s,end_s,text}], language}` at endpoint
    - `{type: 'fallback', fallback: 'web_speech'}` if worker ASR unavailable

### Privacy Processing
- `POST /privacy/process {ticket_id}` - Process photo_original for face/plate blurring

### Analysis
- `POST /analyze` - Text analysis, categorization, urgency, deduplication, evidence linking
  - Input: `{ticket_id, text, language, spans, gps, image_embed}`
  - Output: AnalysisOut with category, urgency, department, location, missing, conflicts, dup_score, parent_id, status, packet_draft

### DAK (Direct Agent Komunikasi)
- `POST /dak/preview {ticket_id}` - Create DAK message preview (draft)
- `POST /dak/approve {msg_id}` - Approve DAK message for sending
- `POST /dispatch_attempt {ticket_id}` - ALWAYS returns 403 {error: 'policy_locked'} (R2 compliance)

### Evaluation
- `POST /eval/run` - Run end-to-end evaluation on seeds/seeds.json

### Audit
- `GET /audit/tickets/{ticket_id}` - Get audit log for specific ticket
- `GET /audit/recent` - Get recent audit entries
- `GET /audit/stats` - Get audit log statistics

## Model Warmup
On startup, the worker loads the following models (warmup):
- Whisper model is loaded once during startup):
1. **Whisper ASR** (`faster_whisper.WhisperModel`) - int8 quantized for CPU efficiency
2. **Silero VAD** (ONNX) - Voice activity detection for speech endpointing
3. **MediaPipe Face Detection** - For facial recognition and blurring
4. **EasyOCR** - For license plate text detection (Indian plate patterns)
5. **Sentence Transformers** (`all-MiniLM-L6-v2`) - For text and image embeddings

Warmup times are reported in the `/health` endpoint.

## Database Schema
See `supabase/migrations/001_init.sql` for complete schema including:
- `profiles`: Operator/supervisor roles
- `tickets`: Complaint tracking with status flow
- `evidence`: All evidence types (original/blurred photos, audio, transcripts, GPS, text)
- `claim_links`: Links between ticket fields and evidence
- `audit_log`: Append-only audit trail (R6 compliance)
- `outbox_msgs`: DAK message queue
- `eval_runs`: Evaluation results
- Row Level Security (RLS) policies for data protection
- Realtime publication for live updates

## Storage Buckets
All buckets are PRIVATE:
1. **originals**: Write-once original files (service_role only)
   - Contains original audio, photos with EXIF GPS preserved
   - No anon/authenticated access
   - SHA256 hash stored for integrity

2. **blurred**: Blurred faces/plates (service_role insert, authenticated staff select)
   - EXIF stripped
   - Faces pixelated (block = max(12, box_w//12))
   - License plates Gaussian blurred
   - Used for DAK message previews

3. **outbox**: DAK message payloads (service_role only)
   - Stores approved message payloads for sending

## Security & Privacy Compliance
All operations comply with AIA33 constraints (R1-R8):

**R1**: No auto-close/delete complaints - duplicates go to 'tray' status + parent link
**R2**: `/dispatch_attempt` ALWAYS returns 403 + audit 'policy_violation_blocked'
**R3**: Blur faces + vehicle plates by default; originals write-once + supervisor-only view
**R4**: LLM receives citizen text ONLY inside `---UNTRUSTED_DATA---` delimiters
**R5**: Service/LLM/WhatsApp keys server-side only; frontend gets anon key + RLS
**R6**: No PII in trace/logs - summaries only (faces=2, plates=1, conf=0.91)
**R7**: No real external sends - DAK writes sandbox channel rows
**R8**: Audio never leaves worker memory except write-once originals upload

## Latency Budgets (CPU Target)
- WS ASR partials: <400 ms
- WS ASR final: <1 s
- Blur processing: <500 ms
- `/analyze` endpoint: <2.5 s

## Fallback Matrix
- **ASR down**: Emit `{type: 'fallback', fallback: 'web_speech'}`
- **LLM down**: Rule-based template → flagged UNCERTAIN
- **Face detector fail**: `blur_unverified=true` (audit, never silently skip)
- **Embeddings fail**: Geo+time-only dup scoring with confidence capped at 0.6

## Testing
Run tests with:
```bash
pytest tests/
```

Test files:
- `test_policy.py`: RLS policies, dispatch restrictions, security
- `test_schema.py`: AnalysisOut validation, fallback behavior
- `test_dup.py`: Deduplication scoring bands, HIGH urgency override
- `test_eval_dry.py`: Evaluation runner metrics verification

## Development Guidelines
1. **Never** send raw audio to LLM (R8)
2. **Always** wrap citizen text in `---UNTRUSTED_DATA---` delimiters for LLM (R4)
3. **Always** blur faces/plates by default (R3)
4. **Never** store PII in logs/audit (R6)
5. **Always** use service_role keys server-side only (R5)
6. **Never** dispatch without explicit human approval (R2)
7. **Verified** blur processing - never skip verification (R3)
8. **Append-only** audit logs - no updates/deletes allowed

## Project Structure
```
SAKSHI/
├── .env.example
├── AGENTS.md
├── CONTRACTS.md
├── README-worker.md
├── requirements.txt
├── seeds/
│   └── seeds.json
├── supabase/
│   ├── migrations/
│   │   └── 001_init.sql
│   └── functions/
│       └── send-dak/
│           └── index.ts
├── tests/
│   ├── test_policy.py
│   ├── test_schema.py
│   ├── test_dup.py
│   └── test_eval_dry.py
└── worker/
    ├── __init__.py
    ├── main.py
    ├── asr.py
    ├── privacy.py
    ├── analyze.py
    ├── dak.py
    ├── evalrun.py
    ├── audit.py
    ├── fallbacks.py
    └── schemas.py
```

## Definition of Done
Verify all before considering complete:
- [ ] Migration applies clean; RLS matrix passes test_policy.py
- [ ] WS stream → partials <400 ms, final <1 s on CPU; audio hashed write-once
- [ ] Blur <500 ms; blurred has no EXIF; originals supervisor-only
- [ ] /analyze <2.5 s; claim_links present for all 4 fields; UNTRUSTED_DATA in prompt log
- [ ] Dup bands + HIGH override behave per seeds; tray restorable via status update
- [ ] DAK draft→approve→sent via edge fn; scope denial audited
- [ ] Dispatch always 403; audit append-only rules block update/delete
- [ ] Eval returns 4 metrics; AGENTS.md + CONTRACTS.md committed

After DoD: Output summary + contract confirmation + merge note (branch be/core; frontends consume CONTRACTS.md)