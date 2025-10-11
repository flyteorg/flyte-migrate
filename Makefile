# Default target: show all available targets
.PHONY: help
help:
	@echo "Available targets:"
	@awk '/^[a-zA-Z0-9_\-]+:/ && !/^\./ {print "  " $$1}' $(MAKEFILE_LIST) | sed 's/://'

.DEFAULT_GOAL := help

.PHONY: fmt
fmt:
	ruff format
	ruff check . --fix
