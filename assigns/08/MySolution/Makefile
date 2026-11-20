# Run from MySolution/.  See README.md.
PYTHON ?= .venv/bin/python
NODE   ?= node

.PHONY: venv test test-fast test-python test-js typecheck run clean

venv:
	python3.12 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt

test: test-python test-js          ## everything, including the two ~30 s 8x8 runs

test-fast:                         ## skips the two full 8x8 runs
	QUEENS_SKIP_SLOW=1 $(PYTHON) -m unittest discover -s tests -v
	$(NODE) --test tests/client/*.test.mjs

test-python:
	$(PYTHON) -m unittest discover -s tests -v

test-js:
	$(NODE) --test tests/client/*.test.mjs

typecheck:
	.venv/bin/mypy

run:
	$(PYTHON) -m queens_rpc

clean:
	rm -rf __pycache__ */__pycache__ .mypy_cache
