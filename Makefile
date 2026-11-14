.PHONY: help install check lint format typecheck test test-unit test-integration

help:              ## Show the available targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

install:           ## Install the package and the dev tools (the dev container does this on creation)
	pip install --user -e '.[dev]'

check:             ## Check that MongoDB (replica set) and Redis are reachable
	python scripts/check_environment.py

lint:              ## Lint and check formatting with ruff
	ruff check .
	ruff format --check .

format:            ## Fix lint issues and format the code with ruff
	ruff check --fix .
	ruff format .

typecheck:         ## Static type check with mypy
	mypy

test:              ## Run all tests (unit + integration)
	pytest

test-unit:         ## Run the tests that do not need the database engines
	pytest -m unit

test-integration:  ## Run the tests against MongoDB and Redis
	pytest -m integration
