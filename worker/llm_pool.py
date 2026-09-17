"""Bounded OpenRouter key rotation with explicit cooldowns."""
from __future__ import annotations

import itertools
import os
import time
from typing import Any

import httpx

KEYS = [key.strip() for key in os.getenv("OPENROUTER_KEYS", "").split(",") if key.strip()]
MODEL = os.getenv("LLM_MODEL", "z-ai/glm-5.2")
_cooldown = {key: 0.0 for key in KEYS}
_cycle = itertools.cycle(KEYS) if KEYS else None


def _next() -> str:
    if not _cycle:
        raise RuntimeError("no OpenRouter keys configured")
    for _ in KEYS:
        key = next(_cycle)
        if time.time() >= _cooldown[key]:
            return key
    raise RuntimeError("all OpenRouter keys in cooldown")


def chat_json(messages: list[dict[str, Any]], timeout: float = 20, client: httpx.Client | None = None) -> str:
    last: Exception | None = None
    for _ in range(max(1, len(KEYS) * 2)):
        try:
            key = _next()
            request = client or httpx.Client(timeout=timeout)
            response = request.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": MODEL, "messages": messages, "temperature": 0,
                      "response_format": {"type": "json_object"}},
            )
            if client is None:
                request.close()
            if response.status_code in (401, 402):
                _cooldown[key] = time.time() + 3600
                continue
            if response.status_code == 429:
                _cooldown[key] = time.time() + 60
                continue
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as error:
            last = error
            if KEYS:
                _cooldown[key] = time.time() + 30
    raise last or RuntimeError("no OpenRouter keys configured")
