# SAKSHI state audit — 2026-09-17

## Evidence collected

- `python3 -m compileall -q worker tests`: **PASS** (syntax only).
- `pytest`: **not run** — the active Python 3.14 installation has no pytest or
  project dependencies installed. Runtime compatibility with the documented Python
  3.11 target is therefore unverified.
- `supabase db push --dry-run`: **PASS**. The connected Supabase project has no
  recorded copies of `001_init.sql` or `002_sim.sql`; both would be applied.
- The OpenRouter model catalogue contains `z-ai/glm-5.2`; the old `zai/glm-5.2`
  spelling is invalid.

## File inventory

| Path | Exists | Compiles / parses | Contract assessment |
| --- | --- | --- | --- |
| `AGENTS.md` | yes | n/a | authoritative R1–R8 rules present |
| `CONTRACTS.md` | yes | n/a | authoritative endpoint/schema contract present |
| `README-worker.md` | yes | n/a | stale: states features are complete although most are placeholders |
| `.env.example` | yes | n/a | updated for the OpenRouter pool; Supabase runtime values still intentionally absent |
| `.gitignore` | yes | n/a | correctly excludes `.env` |
| `.mcp.json` | yes | valid JSON | Supabase remote-MCP endpoint configured; OAuth connection is still required |
| `requirements.txt` | yes | n/a | unpinned; uninstalled in the active interpreter |
| `seeds/seeds.json` | yes | valid JSON | seed data exists |
| `seeds/media/README-media.md` | yes | n/a | actual voice/photo test media absent |
| `worker/main.py` | yes | syntax pass | **not contract-safe**: three duplicate dispatch routes; the final effective route omits the required audit write |
| `worker/analyze.py` | yes | syntax pass | **not contract-safe**: no LLM call, undefined `high_dup_override`, placeholder embeddings/evidence, and PII-bearing error audit entries |
| `worker/asr.py` | yes | syntax pass | **not implemented**: simulated ASR, no write-once audio persistence |
| `worker/privacy.py` | yes | syntax pass | **not implemented**: simulated face/plate processing, hashes, and storage writes |
| `worker/dak.py` | yes | syntax pass | **not contract-safe**: trusts forgeable role header and uses placeholder identity/URL |
| `worker/audit.py` | yes | syntax pass | **not contract-safe**: bearer token is not validated; ticket filtering is in-memory |
| `worker/evalrun.py` | yes | syntax pass | **not implemented**: constant metrics and an absolute workstation path |
| `worker/fallbacks.py` | yes | syntax pass | usable rule fallback, but not wired as the LLM failure path |
| `worker/schemas.py` | yes | syntax pass | shape is broadly aligned; constraints are incomplete |
| `supabase/migrations/001_init.sql` | yes | dry-run accepted | tables/RLS baseline exists; buckets are only comments, not created |
| `supabase/migrations/002_sim.sql` | yes | dry-run accepted | `channel_msgs`, RLS, and Realtime are present but unapplied |
| `supabase/functions/send-dak/index.ts` | yes | unverified (no Deno check) | simulator logic exists but remains undeployed and needs authorization/idempotency review |
| `scripts/setup_supabase.sh` | yes | shell syntax unverified | **broken for CLI 2.117**: it calls unavailable `storage create`, `auth admin`, and `db execute` commands |
| `scripts/verify.sh` | yes | shell syntax unverified | **not a verifier**: it writes simulated PASS rows instead of executing checks |
| `scripts/ws_client.py` | yes | syntax pass | usable harness shape; logs raw transcript text, which violates R6 for production diagnostics |
| `tests/test_policy.py` | yes | syntax pass | test intent exists; cannot run in current interpreter |
| `tests/test_schema.py` | yes | syntax pass | test intent exists; cannot run in current interpreter |
| `tests/test_dup.py` | yes | syntax pass | test intent exists; cannot run in current interpreter |
| `tests/test_eval_dry.py` | yes | syntax pass | test intent exists; cannot run in current interpreter |

## Gap list reconciliation

| Requested gap | Current state |
| --- | --- |
| `send-dak` edge function | source exists; undeployed/unverified |
| `channel_msgs` table | migration exists; unapplied/unverified |
| bucket creation | no working implementation; current script calls unsupported CLI commands |
| demo auth users | no working implementation; current script calls unsupported CLI commands |
| verification script | exists but is placeholder-only |
| WebSocket client | exists, unverified, and must avoid production PII output |
| round-robin LLM pool | missing |
| `/demo/reset` DEMO_MODE gate | gate exists; reset itself is a placeholder |

## Rule-violation findings

1. **R2 (critical):** `worker/main.py` declares `/dispatch_attempt/{ticket_id}` three
   times. FastAPI keeps the final handler, which returns 403 but does **not** write
   `policy_violation_blocked` to the audit log.
2. **R3 (critical):** `worker/privacy.py` returns simulated blur success without
   downloading evidence, detecting redactions, stripping EXIF, uploading a blurred
   copy, or creating immutable evidence records.
3. **R4 (critical):** `/analyze` never calls an LLM or sends delimiter-wrapped text;
   it uses an inline fallback. Its duplicate branch also raises `NameError` whenever
   the score exceeds 0.85.
4. **R5 (high):** no tracked source contains a raw secret and service-role usage is
   server-side. However, worker authorization trusts an `x-supabase-role` request
   header rather than verified Supabase claims, allowing privilege spoofing.
5. **R6 (high):** several audit error paths persist `str(e)`, which can include user
   input or provider details. `ws_client.py` prints transcripts, so it must be
   restricted to local test use or redacted.
6. **R7 (high):** the edge-function source has a simulator path, but it is not
   deployed or verified; DAK preview uses a fake signed URL.
7. **R8 (high):** ASR is simulated. The required write-once audio behavior and
   proof that audio never reaches the LLM do not exist.
8. **R1:** no API DELETE endpoint was found. The `evidence.ticket_id ... on delete
   cascade` relation needs an explicit database-level complaint-deletion guard.
9. **Operational:** the worker boot sequence logs raw exception strings and attempts
   unavailable model files; health readiness is not a meaningful readiness signal.

## Remediation plan

1. Stabilize the worker before any demo: remove duplicate routes; add one audited,
   unconditional 403 dispatch handler; replace forgeable header authorization with
   validated Supabase JWT/role checks; redact all audit and log errors.
2. Add `worker/llm_pool.py` with the verified `z-ai/glm-5.2` OpenRouter pool;
   route `/analyze` through delimiter-wrapped, schema-validated output and the
   existing fallback on total failure. Add a focused pool/analysis test.
3. Replace ASR, privacy, DAK, reset, and evaluation placeholders with real,
   contract-compliant implementations; avoid fake success paths.
4. Correct the schema in new migrations: create private buckets and their policies,
   preserve RLS, add deletion protection, make sender processing idempotent, and
   enable Realtime only after verifying all table policies.
5. Replace `setup_supabase.sh` with supported CLI/API operations, create demo users
   idempotently, deploy `send-dak`, and configure only server-side secrets.
6. Install the documented Python 3.11 environment and dependencies, run `pytest -q`,
   then run a real verifier which measures each endpoint rather than fabricating
   PASS results.
7. After tests pass, apply migrations and deploy to the identified project; create
   buckets/demo users, run the end-to-end verification, inspect RLS advisors, and
   commit the measured `VERIFY.md`.

## MCP connection status

The project now contains a Supabase MCP endpoint configuration, but it is **not
connected in this Codex session**: Supabase MCP requires an interactive OAuth flow;
the supplied personal access token was verified through the Supabase CLI/API path
instead.
