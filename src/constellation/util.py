from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


Json = dict[str, Any]


def now_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(value: str, *, max_len: int = 64) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:max_len].rstrip("_") or "item"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def compact_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def source_span(text: str, *needles: str, width: int = 360) -> str:
    lowered = text.lower()
    for needle in needles:
        idx = lowered.find(needle.lower())
        if idx >= 0:
            start = max(0, idx - width // 3)
            end = min(len(text), idx + width)
            return compact_ws(text[start:end])
    return compact_ws(text[:width])

