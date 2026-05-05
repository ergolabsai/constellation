"""Tests for successful-response LLM cache helpers."""
from __future__ import annotations

from pathlib import Path

from constellation.llm_cache import lookup, write_success
from constellation.paths import Run


class FakeLLM:
    model = "test-model"


def _run(tmp_path: Path) -> Run:
    root = tmp_path / "runs" / "toy"
    root.mkdir(parents=True)
    return Run(root)


def test_llm_cache_round_trip(tmp_path: Path):
    run = _run(tmp_path)
    messages = [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]

    miss = lookup(
        run=run,
        stage="stage_test",
        llm=FakeLLM(),  # type: ignore[arg-type]
        system="system prompt",
        messages=messages,
        max_tokens=128,
    )
    assert not miss.hit

    write_success(
        miss,
        raw_response='{"ok": true}',
        parsed_response={"ok": True},
    )

    hit = lookup(
        run=run,
        stage="stage_test",
        llm=FakeLLM(),  # type: ignore[arg-type]
        system="system prompt",
        messages=messages,
        max_tokens=128,
    )
    assert hit.hit
    assert hit.raw_response == '{"ok": true}'
    assert hit.parsed_response == {"ok": True}


def test_llm_cache_key_changes_with_payload(tmp_path: Path):
    run = _run(tmp_path)
    llm = FakeLLM()  # type: ignore[assignment]
    base = lookup(
        run=run,
        stage="stage_test",
        llm=llm,
        system="system prompt",
        messages=[{"role": "user", "content": [{"type": "text", "text": "a"}]}],
        max_tokens=128,
    )
    changed = lookup(
        run=run,
        stage="stage_test",
        llm=llm,
        system="system prompt",
        messages=[{"role": "user", "content": [{"type": "text", "text": "b"}]}],
        max_tokens=128,
    )

    assert base.key != changed.key
    assert base.path != changed.path
