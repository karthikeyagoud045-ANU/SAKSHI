"""Storage boundary for offline development and Supabase production deployments."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class LocalStorage:
    def __init__(self, root: str = ".localstore") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.data = {"audit": [], "tickets": {}, "outbox": {}, "channel": [], "evidence": []}

    def _put(self, bucket: str, path: str, data: bytes) -> dict[str, str]:
        target = self.root / bucket / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if bucket == "originals" and target.exists():
            raise FileExistsError("original evidence is write-once")
        target.write_bytes(data)
        return {"path": f"{bucket}/{path}", "sha256": hashlib.sha256(data).hexdigest()}

    def put_original(self, path: str, data: bytes) -> dict[str, str]:
        return self._put("originals", path, data)

    def put_blurred(self, path: str, data: bytes) -> dict[str, str]:
        return self._put("blurred", path, data)

    def put_outbox(self, path: str, data: bytes) -> dict[str, str]:
        return self._put("outbox", path, data)

    def get_signed(self, path: str, expires_in: int = 300) -> str:
        if expires_in > 300:
            raise ValueError("signed URLs may not exceed 300 seconds")
        return f"local://{path}?expires_in={expires_in}"

    def read_outbox(self, path: str) -> dict[str, Any]:
        return json.loads((self.root / path).read_text())

    def audit(self, action: str, detail: dict[str, Any]) -> None:
        self.data["audit"].append({"action": action, "detail": detail})

    def create_outbox(self, message: dict[str, Any]) -> dict[str, Any]:
        self.data["outbox"][message["id"]] = message
        self.put_outbox(f"{message['id']}.json", json.dumps(message).encode())
        return message

    def get_outbox(self, message_id: str) -> dict[str, Any] | None:
        return self.data["outbox"].get(message_id)

    def update_outbox(self, message_id: str, **updates: Any) -> dict[str, Any] | None:
        message = self.get_outbox(message_id)
        if message:
            message.update(updates)
            self.put_outbox(f"{message_id}.json", json.dumps(message).encode())
        return message


class SupabaseStorage(LocalStorage):
    """Production adapter; local state remains available for worker-only metadata."""
    def __init__(self, url: str, service_key: str) -> None:
        super().__init__()
        from supabase import create_client
        self.client = create_client(url, service_key)

    def _put(self, bucket: str, path: str, data: bytes) -> dict[str, str]:
        self.client.storage.from_(bucket).upload(path, data, {"upsert": False})
        return {"path": f"{bucket}/{path}", "sha256": hashlib.sha256(data).hexdigest()}

    def get_signed(self, path: str, expires_in: int = 300) -> str:
        if expires_in > 300:
            raise ValueError("signed URLs may not exceed 300 seconds")
        bucket, name = path.split("/", 1)
        return self.client.storage.from_(bucket).create_signed_url(name, expires_in)["signedURL"]


_store: LocalStorage | None = None


def get_store() -> LocalStorage:
    global _store
    if _store is None:
        mode = os.getenv("STORAGE_MODE", "auto")
        url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        _store = SupabaseStorage(url, key) if mode == "supabase" and url and key else LocalStorage(os.getenv("LOCALSTORE_DIR", ".localstore"))
    return _store


def reset_store() -> LocalStorage:
    global _store
    _store = LocalStorage(os.getenv("LOCALSTORE_DIR", ".localstore"))
    return _store
