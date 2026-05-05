"""Structured per-run failure manifest helpers."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from .paths import Run

FAILURES_SCHEMA = "constellation/failures/v0.1"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _empty_doc() -> dict[str, Any]:
    return {
        "$schema": FAILURES_SCHEMA,
        "updated_at": _now(),
        "failures": {},
    }


def load_failures(run: Run) -> dict[str, Any]:
    """Load the run's failure manifest, or return an empty one."""
    if not run.failures_path.exists():
        return _empty_doc()
    return json.loads(run.failures_path.read_text())


def write_failures(run: Run, doc: dict[str, Any]) -> None:
    """Persist a failure manifest."""
    doc["updated_at"] = _now()
    run.failures_path.write_text(json.dumps(doc, indent=2) + "\n")


def clear_stage_failures(run: Run, stage: str) -> None:
    """Remove stale failures for a stage at the beginning of a rerun."""
    if not run.failures_path.exists():
        return
    doc = load_failures(run)
    failures = doc.setdefault("failures", {})
    failures.pop(stage, None)
    if failures:
        write_failures(run, doc)
    else:
        run.failures_path.unlink()


def append_stage_failures(run: Run, stage: str, entries: list[dict[str, Any]]) -> None:
    """Append one or more failures for `stage`."""
    if not entries:
        return
    doc = load_failures(run)
    failures = doc.setdefault("failures", {})
    failures.setdefault(stage, []).extend(entries)
    write_failures(run, doc)
