PYTHON := .venv/bin/python
PIP_CACHE := .cache/pip
PIP := PIP_CACHE_DIR=$(PIP_CACHE) .venv/bin/python -m pip

.PHONY: setup test smoke clean

setup:
	python3.13 -m venv .venv
	mkdir -p $(PIP_CACHE)
	$(PIP) install -e ".[dev]"

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

smoke:
	$(PYTHON) -m constellation run corpora/shumlak --output runs/shumlak_smoke --force

clean:
	rm -rf .pytest_cache .ruff_cache dist *.egg-info runs/shumlak_smoke
