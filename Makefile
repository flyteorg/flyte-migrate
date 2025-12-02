# Default target: show all available targets
.PHONY: help
help:
	@echo "Available targets:"
	@awk '/^[a-zA-Z0-9_\-]+:/ && !/^\./ {print "  " $$1}' $(MAKEFILE_LIST) | sed 's/://'

.DEFAULT_GOAL := help

.PHONY: fmt
fmt:
	uv run python -m ruff format
	uv run python -m ruff check . --fix

.PHONY: fmt-check
fmt-check:
	uv run python -m ruff format --check
	uv run python -m ruff check .

.PHONY: mypy
mypy:
	uv run python -m mypy --config-file pyproject.toml src/

.PHONY: lint
lint:
	uv run python -m ruff check .

.PHONY: lint-fix
lint-fix:
	uv run python -m ruff check . --fix

.PHONY: dist
dist: clean
	uv run python -m build --wheel --installer uv

.PHONY: clean
clean:
	rm -rf dist/
	rm -rf build/
	rm -rf src/flyte_migrate.egg-info
