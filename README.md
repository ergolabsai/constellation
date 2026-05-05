# Constellation

Constellation is a sheaf-based literature consolidation pipeline. Given a
curated corpus of PDFs, it extracts paper and claim JSON, builds a comparability
complex, generates evidence-faithful claim variants, chooses a MAP global
section, consolidates the result into Ideas, and renders report and
visualization artifacts.

For the project theory and object model, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Requirements

- Python 3.13 or newer
- An Anthropic API key for stages that call the LLM

## Install

Create a local virtual environment and install the package with developer tools:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
```

Copy the example environment file and fill in your key:

```bash
cp .env.example .env
```

`.env` should contain:

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

You can optionally override the model:

```bash
CONSTELLATION_MODEL=claude-sonnet-4-6
```

## Corpus Layout

A corpus is a folder with a `pdfs/` directory:

```text
corpora/
  small_atlas/
    pdfs/
      paper-one.pdf
      paper-two.pdf
```

Pipeline outputs are written to `runs/<corpus>_<utc-timestamp>/`. The `runs/`
directory is ignored by git.

## First Run

Run the full pipeline over a corpus:

```bash
.venv/bin/constellation run corpora/small_atlas
```

The run creates artifacts like:

```text
runs/small_atlas_YYYYMMDDTHHMMSSZ/
  run_config.json
  papers/
  claims/
  tag_vocabulary.json
  tags.json
  comparability_complex.json
  sheaf.json
  ideas/
  epsilon_machine.json
  report.md
  failures.json
  llm_cache/
```

Full runs call the LLM and may take time and API credits. Stages 3, 6, 7, and 9
are pure code; the other stages use the LLM.

`run_config.json` snapshots the model, schema versions, prompt hashes, and stage
parameters used by the run. Existing run configs are reused on resume, so
rerunning later does not silently pick up a different model or threshold from
your environment.

Stage 6 also runs a configurable λ sensitivity sweep using
`stage6_map.lambda_sensitivity_values` from `run_config.json`. The canonical
MAP section still uses `lambda_rewrite_penalty`; `sheaf.json` records which
claim selections are stable across the sweep and which depend on the rewrite
penalty.

`llm_cache/` stores successful parsed and validated LLM JSON responses keyed by
the exact request. Rerunning the same stage with the same model, prompt, payload,
and token budget reuses the cached response.

By default, extraction, tagging, and alternative generation are strict: any
paper, tag batch, or contested-claim alternative failure fails the stage after
recording `failures.json`. For exploratory best-effort runs, edit
`run_config.json` and set the relevant stage's `allow_partial` to `true`.

After Ideas are written, `epsilon_machine.json` records the Idea state
distribution, statistical complexity Cμ, effective state count, and directed
transition graph. The report and visualizer surface these metrics so a run can
show not just whether it is coherent, but how much consolidated theory structure
it contains.

## Resume or Rerun Stages

Use `--resume` with `--from` and `--to` to continue or rerun part of an existing
run:

```bash
.venv/bin/constellation run corpora/small_atlas \
  --resume runs/small_atlas_YYYYMMDDTHHMMSSZ \
  --from 6 \
  --to 9
```

Stage 2 is designed for review: if `tag_vocabulary.json` already exists, the
pipeline reuses it. You can edit that file, then rerun stage 2 to retag claims:

```bash
.venv/bin/constellation run corpora/small_atlas \
  --resume runs/small_atlas_YYYYMMDDTHHMMSSZ \
  --from 2 \
  --to 2
```

## Visualization

Render a self-contained HTML view for a completed run:

```bash
.venv/bin/constellation visualize runs/small_atlas_YYYYMMDDTHHMMSSZ
```

By default this writes:

```text
runs/small_atlas_YYYYMMDDTHHMMSSZ/constellation.html
```

The visualizer opens on an Idea dashboard with Cμ, effective-state, residual,
and λ-sensitivity summaries. The graph modes let you inspect the structural
claim map or filter research-priority next steps by kind, priority, effort, and
maturity.

You can also highlight a synthesis or review paper by `paper_id`:

```bash
.venv/bin/constellation visualize runs/small_atlas_YYYYMMDDTHHMMSSZ \
  --synthesis-paper paper_id_here
```

## Local Checks

Run the same checks used by CI:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
```

## Useful Files

- `ARCHITECTURE.md`: pipeline design and deferred work
- `paper_schema.json`, `claim_schema.json`, `sheaf_schema.json`,
  `idea_schema.json`, `epsilon_machine_schema.json`: source-of-truth artifact
  schemas
- `src/constellation/stages/`: the nine pipeline stages
- `src/constellation/prompts/`: LLM prompts used by extraction, tagging,
  scoring, alternatives, and consolidation
- `scripts/compare_runs.py`: read-only comparison tool for two completed runs
