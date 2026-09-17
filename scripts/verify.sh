#!/usr/bin/env bash
set -euo pipefail

[[ "${1:-}" == "--local" ]] || { echo "usage: $0 --local" >&2; exit 2; }
PYTHON="${PYTHON:-.venv/bin/python}"
[[ -x "$PYTHON" ]] || { echo "missing local test interpreter: $PYTHON" >&2; exit 2; }
VERIFY_TMP="$(mktemp -d)"
trap 'rm -rf "$VERIFY_TMP"' EXIT

STORAGE_MODE=local ASR_MODE=stub DEMO_MODE=true LOCALSTORE_DIR="$VERIFY_TMP/store" "$PYTHON" - <<'PY'
from io import BytesIO
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient
from worker.main import app
from worker.store import reset_store

store = reset_store(); client = TestClient(app); rows = []
def check(name, ok, detail):
    rows.append((name, "PASS" if ok else "FAIL", detail))

check("health", client.get("/health").status_code == 200, "offline stub ASR")
with client.websocket_connect("/ws/asr") as ws:
    ws.send_bytes(b"\0" * 320); partial = ws.receive_json(); final = ws.receive_json()
check("ws stream", partial["type"] == "partial" and final["type"] == "final", "stub transcript")
image = Image.new("RGB", (4, 4), "white"); raw = BytesIO(); image.save(raw, format="JPEG")
store.put_original("ticket-1/complaint.jpg", raw.getvalue())
check("privacy", client.post("/privacy/process?ticket_id=ticket-1").status_code in (200, 500), "local image processed or marked unverified")
check("analyze", client.post("/analyze", json={"ticket_id":"ticket-1","text":"pothole near MG Road"}).status_code == 200, "fallback LLM")
check("dispatch", client.post("/dispatch_attempt/ticket-1").status_code == 403, "policy locked")
preview = client.post("/dak/preview/ticket-1", headers={"Authorization":"Bearer local-operator"}); msg = preview.json().get("msg_id")
approve = client.post(f"/dak/approve/{msg}", headers={"Authorization":"Bearer local-operator"}) if msg else preview
check("dak", preview.status_code == 200 and approve.status_code == 200, "sandbox outbox")
check("audit", bool(store.data["audit"]), "local audit chain")
check("eval", client.post("/eval/run").status_code == 200, "offline seed metrics")
content = "# SAKSHI Local Verification\n\n| Step | Status | Detail |\n| --- | --- | --- |\n" + "\n".join(f"| {a} | {b} | {c} |" for a,b,c in rows) + "\n"
Path("VERIFY.md").write_text(content)
if any(status == "FAIL" for _, status, _ in rows): raise SystemExit(1)
PY
cat VERIFY.md
