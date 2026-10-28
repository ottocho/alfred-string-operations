.DEFAULT_GOAL := build

UV ?= uv
PYTHON = $(UV) run --no-project --no-config --offline --no-python-downloads --python ">=3.10" python -B

.PHONY: build install test

build:
	$(PYTHON) scripts/build.py

install: build
	open dist/String-Operations.alfredworkflow

test:
	$(PYTHON) -m unittest discover -s tests -v
