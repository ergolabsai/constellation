"""Orchestrator: runs pipeline stages in sequence over a corpus.

Each stage reads the prior stages' artifacts from the run directory and
writes its own. Stages can be re-run individually via --from / --to.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from rich.console import Console

from .paths import Corpus, Run
from .stages import (
    s1_extract,
    s2_tag,
    s3_complex,
    s4_alternatives,
    s5_compatibility,
    s6_map,
    s7_frustration,
    s8_consolidate,
    s9_report,
)

console = Console()


@dataclass
class Stage:
    n: int
    name: str
    fn: Callable[[Corpus, Run], None]


STAGES: list[Stage] = [
    Stage(1, "extract", s1_extract.run),
    Stage(2, "tag", s2_tag.run),
    Stage(3, "complex", s3_complex.run),
    Stage(4, "alternatives", s4_alternatives.run),
    Stage(5, "compatibility", s5_compatibility.run),
    Stage(6, "map", s6_map.run),
    Stage(7, "frustration", s7_frustration.run),
    Stage(8, "consolidate", s8_consolidate.run),
    Stage(9, "report", s9_report.run),
]


def run_pipeline(
    corpus: Corpus,
    run_obj: Run,
    *,
    from_stage: int = 1,
    to_stage: int = 9,
) -> None:
    run_obj.ensure_dirs()
    for stage in STAGES:
        if not (from_stage <= stage.n <= to_stage):
            continue
        console.rule(f"[bold]Stage {stage.n}: {stage.name}[/bold]")
        stage.fn(corpus, run_obj)
        console.print(f"[green]done[/green] stage {stage.n}: {stage.name}")
