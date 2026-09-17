# Deletion audit — commit 9082910

## Result

No tracked file was fully deleted and no existing test function was removed.
`supabase/`, `seeds/`, `AGENTS.md`, and `CONTRACTS.md` are unchanged by the
commit.

## Removed/replaced code

| Removed item | Replacement / justification |
| --- | --- |
| Three `dispatch_attempt` declarations | One route in `worker/main.py` with an unconditional 403 and `policy_violation_blocked` audit write; covered by `test_single_dispatch_route.py`. |
| Per-module `init_supabase` globals in worker routes | `worker/store.py` storage boundary; missing Supabase configuration now falls back to local storage. |
| Inline `analyze.rule_template_fallback` | Canonical `worker.fallbacks.rule_template_fallback`; prevents duplicate fallback logic. |
| Placeholder ASR, privacy, DAK, evaluation, and verifier bodies | Smaller offline-safe implementations and explicit stub/fallback status. |
| Header-only service-role approval path | A local fake-auth boundary for offline tests; production Supabase JWT verification remains a remote-mode follow-up. |

## Contract endpoint verification

Direct endpoint exercises confirmed all nine routes are registered and reachable:

| Contract route | Result |
| --- | --- |
| `GET /health` | 200 |
| `POST /demo/reset` | 403 when `DEMO_MODE` is false (expected gate) |
| `WS /ws/asr` | connected and emitted stub messages |
| `POST /privacy/process` | 404 for missing original evidence (route reached) |
| `POST /analyze` | 200 |
| `POST /dak/preview` | 200 with local test session |
| `POST /dak/approve` | 404 for unknown message (route reached) |
| `POST /dispatch_attempt` | 403 |
| `POST /eval/run` | 200 |

FastAPI 0.141 stores included routers behind internal `_IncludedRouter` wrappers,
so a naive `app.routes` path enumeration omits nested route paths. Actual request
verification above is the authoritative route check.

## Rule-enforcement audit

- R2: one dispatch route writes `policy_violation_blocked` through the store.
- R4: LLM input is bounded by `UNTRUSTED_DATA` delimiters and falls back on error.
- R3: privacy records `blur_unverified` whenever detectors cannot run.
- R6: audit details are reduced to ticket IDs, counts, hashes, and status reasons.
- R7: DAK remains local outbox-only in offline mode.

## Pytest warnings

`pytest -q` passes 18 tests with two warnings. Treating `DeprecationWarning` as
an error fails during import in third-party `fastapi.testclient`/Starlette because
Starlette 1.6 accesses deprecated `anyio.abc.BlockingPortal`; it is not emitted
by application code. The local suite cannot truthfully be warning-free until a
compatible FastAPI/Starlette/AnyIO version set is selected and verified.
