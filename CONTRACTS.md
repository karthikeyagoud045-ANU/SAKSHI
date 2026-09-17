# SAKSHI Backend Contracts

## Endpoint Signatures

### WebSocket Endpoints
- `WS /ws/asr`: Accept binary PCM16 16kHz chunks (2–4 s). 
  - Input: Binary audio chunks
  - Output: JSON messages:
    - `{type: 'partial', text}` per chunk
    - `{type: 'final', text, spans:[{start_s,end_s,text}], language}` at endpoint
    - `{type: 'fallback', fallback: 'web_speech'}` if worker ASR unavailable

### HTTP Endpoints
- `POST /privacy/process {ticket_id}` 
  - Input: `{ticket_id: string}`
  - Output: `{success: boolean}`
  - Processes photo_original → photo_blurred with face/plate blurring

- `POST /analyze` (TextInput → AnalysisOut)
  - Input: 
    ```json
    {
      "ticket_id": "uuid",
      "text": "string",
      "language": "string (default: 'auto')",
      "spans": "array of {start_s:number, end_s:number, text:string}",
      "gps": "{lat:number, lng:number} | null",
      "image_embed": "array of numbers | null"
    }
    ```
  - Output:
    ```json
    {
      "category": {"value": "string", "confidence": "number"},
      "urgency": {"value": "string (LOW|MEDIUM|HIGH)", "confidence": "number"},
      "department": {"value": "string", "confidence": "number"},
      "location": {"value": "{lat:number, lng:number}", "confidence": "number"},
      "missing": "string[]",
      "conflicts": "any[]",
      "dup_score": "number",
      "parent_id": "uuid | null",
      "status": "string (intake|triage|tray|merged|human_review|approved|sent)",
      "packet_draft": "object"
    }
    ```

- `POST /dak/preview {ticket_id}`
  - Input: `{ticket_id: string}`
  - Output: `{msg_id: string}` (creates outbox_msgs row with status 'draft')

- `POST /dak/approve {msg_id}` (authenticated)
  - Input: `{msg_id: string}`
  - Output: `{success: boolean}` (sets status 'approved')

- `POST /dispatch_attempt {ticket_id}` → ALWAYS returns HTTP 403
  - Input: `{ticket_id: string}`
  - Output: 
    ```json
    {
      "error": "policy_locked"
    }
    ```
  - Always writes audit 'policy_violation_blocked'

- `POST /eval/run`
  - Input: None (uses seeds/seeds.json)
  - Output: 
    ```json
    {
      "task_completion": "number",
      "dup_precision": "number", 
      "dup_recall": "number",
      "urgency_agreement": "number"
    }
    ```

- `GET /health`
  - Input: None
  - Output: 
    ```json
    {
      "ready": "boolean",
      "models": {
        "name": "ms_warmup"
      }
    }
    ```

- `POST /demo/reset` (only if DEMO_MODE=true)
  - Input: None
  - Output: `{success: boolean}` (reseeds from seeds/seeds.json)

## Table Schemas

### profiles
- `id`: uuid (primary key, references auth.users)
- `role`: text (check: role in ('operator','supervisor'))

### tickets
- `id`: uuid (primary key, default gen_random_uuid())
- `tracking_code`: text (unique, not null, default upper(substr(md5(random()::text),1,6)))
- `category`: text
- `urgency`: text (check: urgency in ('LOW','MEDIUM','HIGH'))
- `dept`: text
- `loc_lat`: float8
- `loc_lng`: float8
- `loc_conf`: float8
- `status`: text (not null, default 'intake', check: status in ('intake','triage','tray','merged','human_review','approved','sent'))
- `dup_score`: float8
- `parent_id`: uuid (references tickets(id))
- `missing`: text[]
- `conflicts`: jsonb
- `created_at`: timestamptz (not null, default now())

### evidence
- `id`: uuid (primary key, default gen_random_uuid())
- `ticket_id`: uuid (not null, references tickets(id) on delete cascade)
- `kind`: text (not null, check: kind in ('photo_original','photo_blurred','audio','transcript','gps','text'))
- `storage_path`: text
- `span`: tsrange
- `meta`: jsonb (not null, default '{}')
- `sha256`: text (not null)
- `created_at`: timestamptz (not null, default now())

### claim_links
- `id`: uuid (primary key, default gen_random_uuid())
- `ticket_id`: uuid (not null, references tickets(id))
- `field`: text (not null)
- `value`: text (not null)
- `evidence_id`: uuid (not null, references evidence(id))
- `conf`: float8 (not null)

### audit_log
- `id`: bigserial (primary key)
- `ts`: timestamptz (not null, default now())
- `actor`: text (not null)
- `action`: text (not null)
- `detail`: jsonb (not null, default '{}')
- Rules: 
  - `audit_no_update`: on update to audit_log do instead nothing
  - `audit_no_delete`: on delete to audit_log do instead nothing

### outbox_msgs
- `id`: uuid (primary key, default gen_random_uuid())
- `ticket_id`: uuid (not null, references tickets(id))
- `payload`: jsonb (not null)
- `status`: text (not null, default 'draft', check: status in ('draft','approved','sent','rejected'))
- `approved_by`: uuid (references auth.users(id))
- `sent_at`: timestamptz

### channel_msgs
- `id`: uuid (primary key, default gen_random_uuid())
- `msg_id`: uuid (not null, references outbox_msgs(id))
- `bubble`: jsonb (not null)
- `ticks`: int (not null, default 1)
- `ts`: timestamptz (not null, default now())

### eval_runs
- `id`: uuid (primary key, default gen_random_uuid())
- `seed_id`: text (not null)
- `metrics`: jsonb (not null)
- `ts`: timestamptz (not null, default now())

## Realtime Publication Tables
- tickets
- audit_log
- outbox_msgs
- channel_msgs

## Storage Buckets (all PRIVATE)
1. **originals**: 
   - No anon/authenticated insert or select policies (service_role only)
   - Stores write-once original files with SHA256
   - EXIF GPS kept in evidence.meta ONLY
   - SHA256 hash stored for integrity

2. **blurred**:
   - Select for authenticated staff
   - Insert service_role only
   - Stores blurred faces/plates (EXIF stripped)
   - Faces pixelated (block = max(12, box_w//12))
   - License plates Gaussian blurred
   - Used for DAK message previews

3. **outbox**:
   - Select/update service_role only (sender edge fn + worker)
   - Stores DAK message payloads

## Signed URLs
- All signed URLs in worker code expire ≤ 300 seconds

## Mock Fixture Shapes (for frontend development)
Located in `web/mocks/*.json`

### ticket.json
```json
{
  "id": "uuid",
  "tracking_code": "ABC123",
  "category": "pothole",
  "urgency": "MEDIUM",
  "dept": "public_works",
  "loc_lat": 12.9716,
  "loc_lng": 77.5946,
  "loc_conf": 0.85,
  "status": "intake",
  "dup_score": null,
  "parent_id": null,
  "missing": [],
  "conflicts": null,
  "created_at": "2026-09-17T08:13:50Z"
}
```

### evidence.json
```json
{
  "id": "uuid",
  "ticket_id": "uuid",
  "kind": "photo_original",
  "storage_path": "originals/ticket-id/photo.jpg",
  "span": "[2026-09-17T08:13:50Z,2026-09-17T08:13:50Z]",
  "meta": {"sha256": "abc123...", "exif_gps": {"lat": 12.9716, "lng": 77.5946}},
  "sha256": "abc123...",
  "created_at": "2026-09-17T08:13:50Z"
}
```

### outbox_msg.json
```json
{
  "id": "uuid",
  "ticket_id": "uuid",
  "payload": {
    "blurred_signed_path_placeholder": "https://example.com/blurred.jpg",
    "text_summary": "Pothole on Main Street",
    "lat": 12.9716,
    "lng": 77.5946,
    "packet_id": "uuid",
    "order": ["image","text","pin"]
  },
  "status": "draft",
  "approved_by": null,
  "sent_at": null
}
```

### channel_msg.json
```json
{
  "id": "uuid",
  "msg_id": "uuid",
  "bubble": {
    "type": "dak_message",
    "ticket_id": "uuid",
    "payload": {
      "blurred_signed_path_placeholder": "string",
      "text_summary": "string",
      "lat": "number",
      "lng": "number",
      "packet_id": "string",
      "order": "string[]"
    }
  },
  "ticks": "integer",
  "ts": "timestamp"
}
```
