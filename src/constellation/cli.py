"""CLI entry point.

Subcommands:
  constellation run <corpus_dir>       — full pipeline
  constellation visualize <run_dir>    — render interactive HTML over a run
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .paths import Corpus, Run
from .pipeline import run_pipeline
from .viz import render as render_viz

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()

DEFAULT_RUNS_ROOT = Path("runs")


@app.command()
def run(
    corpus_dir: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, dir_okay=True)
    ],
    from_stage: Annotated[int, typer.Option("--from", min=1, max=9)] = 1,
    to_stage: Annotated[int, typer.Option("--to", min=1, max=9)] = 9,
    runs_root: Annotated[Path, typer.Option("--runs-root")] = DEFAULT_RUNS_ROOT,
    resume: Annotated[
        Path | None,
        typer.Option(
            "--resume",
            help="Re-use an existing run directory instead of creating a new one",
        ),
    ] = None,
) -> None:
    """Run the Landscape Map v2 pipeline over a corpus directory.

    The corpus directory must contain a `pdfs/` subfolder with at least one PDF.
    Output is written to runs/<corpus>_<utc-timestamp>/ unless --resume is given.
    """
    corpus = Corpus(root=corpus_dir.resolve())
    if not corpus.pdfs():
        console.print(f"[red]no PDFs found in {corpus.pdfs_dir}[/red]")
        raise typer.Exit(1)

    if resume is not None:
        run_obj = Run.existing(resume.resolve())
        console.print(f"resuming run: {run_obj.root}")
    else:
        runs_root.mkdir(parents=True, exist_ok=True)
        run_obj = Run.new(corpus, runs_root.resolve())
        console.print(f"new run: {run_obj.root}")

    console.print(f"corpus: {corpus.name}  ({len(corpus.pdfs())} PDFs)")
    run_pipeline(corpus, run_obj, from_stage=from_stage, to_stage=to_stage)


@app.command()
def visualize(
    run_dir: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, dir_okay=True)
    ],
    out: Annotated[
        Path | None,
        typer.Option(
            "--out",
            help="Output HTML path (default: <run_dir>/constellation.html)",
        ),
    ] = None,
    synthesis_paper: Annotated[
        str | None,
        typer.Option(
            "--synthesis-paper",
            help=(
                "paper_id of a synthesis/review paper to highlight (★ markers + "
                "Idea-coverage panel)"
            ),
        ),
    ] = None,
) -> None:
    """Render an interactive HTML view of a completed pipeline run."""
    run_obj = Run.existing(run_dir.resolve())
    if not run_obj.sheaf_path.exists():
        console.print(f"[red]missing sheaf.json under {run_obj.root}[/red]")
        raise typer.Exit(1)
    if not list(run_obj.ideas_dir.glob("*.json")):
        console.print(f"[red]no ideas under {run_obj.ideas_dir}[/red]")
        raise typer.Exit(1)
    try:
        out_path = render_viz(
            run_obj,
            out_path=out.resolve() if out else None,
            synthesis_paper_id=synthesis_paper,
        )
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    try:
        rel = out_path.relative_to(Path.cwd())
    except ValueError:
        rel = out_path
    console.print(f"[green]→[/green] wrote {rel}")
    console.print(f"  open: file://{out_path}")
    if synthesis_paper:
        console.print(f"  synthesis paper: [yellow]{synthesis_paper}[/yellow] (rendered as ★)")


if __name__ == "__main__":
    app()
