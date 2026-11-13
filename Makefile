PYTHON ?= python3
VENV_PYTHON := .venv/bin/python
CHECK_PYTHON := -c 'import sys; sys.exit("Python 3.12+ is required") if sys.version_info < (3, 12) else None'

.PHONY: help install dev test lint format typecheck audit migrate docs clean up down

help:
	@printf '%s\n' \
		'install    Create .venv and install runtime dependencies and the project' \
		'dev        Install developer tools and configure hooks when available' \
		'test       Run pytest with coverage (install requirements/test.txt first)' \
		'lint       Check Python files with Ruff' \
		'format     Format Python files with Ruff' \
		'typecheck  Run strict MyPy checks' \
		'audit      Audit runtime dependencies with pip-audit' \
		'migrate    Apply Alembic migrations when available' \
		'docs       Export OpenAPI when available' \
		'up         Build and start Docker Compose services when available' \
		'down       Stop Docker Compose services when available' \
		'clean      Remove local environments, caches, and build output' \
		'help       Show this list'

$(VENV_PYTHON):
	$(PYTHON) $(CHECK_PYTHON)
	$(PYTHON) -m venv .venv

install: $(VENV_PYTHON)
	$(VENV_PYTHON) $(CHECK_PYTHON)
	$(VENV_PYTHON) -m pip install -r requirements/base.txt
	$(VENV_PYTHON) -m pip install -e .

dev: install
	$(VENV_PYTHON) -m pip install -r requirements/dev.txt
	@if test -f .pre-commit-config.yaml; then $(VENV_PYTHON) -m pre_commit install; \
	else printf '%s\n' 'Pre-commit setup is pending .pre-commit-config.yaml.'; fi

test:
	$(VENV_PYTHON) -m pytest -v --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=80

lint:
	$(VENV_PYTHON) -m ruff check .

format:
	$(VENV_PYTHON) -m ruff format .

typecheck:
	$(VENV_PYTHON) -m mypy --strict src/

audit:
	$(VENV_PYTHON) -m pip_audit -r requirements/base.txt

migrate:
	@test -f alembic.ini || { printf '%s\n' 'Alembic configuration is not available yet.' >&2; exit 1; }
	$(VENV_PYTHON) -m alembic upgrade head

docs:
	@test -f scripts/export_openapi.py || { printf '%s\n' 'The OpenAPI exporter is not available yet.' >&2; exit 1; }
	$(VENV_PYTHON) scripts/export_openapi.py

up:
	docker compose up --build -d

down:
	docker compose down

clean:
	rm -rf .venv .mypy_cache .ruff_cache .pytest_cache htmlcov .coverage dist build
	find . -name .git -prune -o -type d -name __pycache__ -prune -exec rm -rf {} +
