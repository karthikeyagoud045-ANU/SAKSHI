# SAKSHI Backend Core Engineering Guidelines

## Non-Negotiable Rules (from AIA33 constraints)
**R1** NEVER auto-close or delete a complaint. Duplicates → status 'tray' + parent link; restorable.
**R2** NEVER dispatch crews or send messages without explicit human approval. `/dispatch_attempt` ALWAYS returns 403 and writes audit 'policy_violation_blocked'.
**R3** Blur faces + vehicle plates by default. Originals write- Originals write-once + sha256; supervisor-only view; every view audits 'original_viewed'. EXIF GPS kept in originals meta ONLY; stripped elsewhere.
**R4** LLM receives citizen text/transcript ONLY inside UNTRUSTED_DATA delimiters; all tool args and LLM JSON schema-validated. Rules (not LLM) own: urgency override, dup auto-link bands, gates.
**R5** service_role / LLM / WhatsApp keys server-side ONLY (env). Frontend gets anon key + RLS only.
**R6** No PII in trace/logs: summaries only (faces=2, plates=1, conf=0.91). Never raw transcript text in audit_log.detail.
**R7** No real external sends. DAK writes sandbox channel rows; Meta Cloud API path = stubbed flag.
**R8** Audio never leaves worker memory except write-once originals upload; never to LLM.

## Ticket Statuses
- `intake`: Initial submission
- `triage`: Initial processing
- `tray`: Duplicate hold (restorable)
- `merged`: Combined with parent ticket
- `human_review`: Requires human intervention
- `approved`: Ready for dispatch
- `sent`: DAK message sent

## Badges (stored as fields)
- `AI-DRAFT`: Initial AI-generated packet
- `HUMAN-APPROVED`: Human-reviewed and approved
- `UNCERTAIN`: Low confidence or fallback used
- `BLURRED`: Faces/plates blurred by default

## Duplicate Scoring Formula
`dup_score = 0.35*cos(MiniLM(text), ticket.text_emb) + 0.25*cos(image_embed, ticket.img_emb) + 0.25*geo_proximity(haversine decay ≤1 km) + 0.15*time_window(decay ≤72 h)`
- Bands: >0.85 → auto-link (status 'tray'); 0.60–0.85 → flagged; HIGH urgency on EITHER ticket → suspend auto-link → status 'human_review'

## Latency Budget (CPU target)
- WS ASR partials: <400 ms
- WS ASR final: <1 s
- Blur processing: <500 ms
- `/analyze` endpoint: <2.5 s

## Stack
- Database: Supabase Postgres
- Storage: Supabase Storage (3 private buckets: originals, blurred, outbox)
- Worker: Python 3.11 FastAPI
- ASR: faster-whisper int8 + Silero VAD (ONNX)
- Privacy: MediaPipe face detection, EasyOCR
- NLP: Sentence-transformers (MiniLM)
- LLM: Structured output with temperature 0
- Realtime: Supabase Realtime (tickets, audit_log, outbox_msgs, channel_msgs)
- Testing: Pytest

## Do-Not List
- ❌ Never auto-close/delete complaints (R1)
- ❌ Never dispatch without human approval (R2)
- ❌ Never send raw audio to LLM (R8)
- ❌ Never store PII in logs/audit (R6)
- ❌ Never expose service_role keys to frontend (R5)
- ❌ Never skip blur verification (R3)
- ❌ Never process LLM input without UNTRUSTED_DATA delimiters (R4)
- ❌ Never make real external sends in dev (R7)
