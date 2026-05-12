# Constellation

Constellation is a fresh implementation of the restriction-rewriting
architecture in [ARCHITECTURE.md](ARCHITECTURE.md).

The current MVP is intentionally small:

- read PDFs from a corpus folder
- extract claim and evidence records
- build sparse claim-evidence prediction edges
- compute residuals on a bipartite sheaf
- rewrite claim scope before touching evidence context
- consolidate the final state into Ideas and a report

The first pass runs without network access or API keys. It uses deterministic
Shumlak corpus seeds plus `pdftotext` provenance snippets so the architecture
can be tested end to end before LLM extraction is reintroduced.

## Run

Create the local environment first:

```bash
make setup
```

This creates `.venv/` with Python 3.13 and installs the project in editable
mode. The MVP has no third-party Python dependencies; it does require the
system `pdftotext` command.

```bash
.venv/bin/constellation run corpora/shumlak --output runs/shumlak_smoke --force
```

Artifacts are written under the run directory:

```text
runs/shumlak_smoke/
  papers/
  claims/
  evidence/
  evidence_comparability.json
  prediction_edges.json
  sheaf.json
  operations.json
  ideas/
  report.md
  constellation.html
```

## Test

```bash
make test
```
