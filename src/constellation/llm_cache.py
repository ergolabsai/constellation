"""Successful-response cache for LLM JSON calls.

Cache entries live under a run directory and are keyed by the exact request
shape: stage, model, system prompt hash, messages hash, and max token budget.
Callers write only after parsing and validation succeed, so malformed model
outputs do not become sticky failures.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from .llm import LLM
from .paths import Run

CACHE_SCHEMA = "constellation/llm_cache/v0.1"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash_text(text: str) -> str:
    return "sha256:" + sha256(text.encode("utf-8")).hexdigest()


def _hash_json(value: Any) -> str:
    return _hash_text(_stable_json(value))


@dataclass(frozen=True)
class LLMCacheHandle:
    """Lookup result plus enough metadata to write a successful response later."""

    path: Path
    key: str
    metadata: dict[str, Any]
    record: dict[str, Any] | None = None

    @property
    def hit(self) -> bool:
        return self.record is not None

    @property
    def raw_response(self) -> str:
        if self.record is None:
            raise ValueError("cache miss has no raw response")
        return str(self.record.get("raw_response", ""))

    @property
    def parsed_response(self) -> Any:
        if self.record is None:
            raise ValueError("cache miss has no parsed response")
        return self.record.get("parsed_response")


def lookup(
    *,
    run: Run,
    stage: str,
    llm: LLM,
    system: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    cache_system: bool = True,
) -> LLMCacheHandle:
    """Return a cache handle for one LLM request."""
    metadata = {
        "$schema": CACHE_SCHEMA,
        "stage": stage,
        "model": llm.model,
        "max_tokens": max_tokens,
        "cache_system": cache_system,
        "system_hash": _hash_text(system),
        "messages_hash": _hash_json(messages),
    }
    key = sha256(_stable_json(metadata).encode("utf-8")).hexdigest()
    path = run.llm_cache_dir / stage / f"{key}.json"
    record = json.loads(path.read_text()) if path.exists() else None
    return LLMCacheHandle(path=path, key=key, metadata=metadata, record=record)


def write_success(
    handle: LLMCacheHandle,
    *,
    raw_response: str,
    parsed_response: Any,
) -> None:
    """Write a successful parsed+validated response to cache."""
    if handle.hit:
        return
    record = {
        **handle.metadata,
        "cache_key": handle.key,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "raw_response": raw_response,
        "parsed_response": parsed_response,
    }
    handle.path.parent.mkdir(parents=True, exist_ok=True)
    handle.path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
