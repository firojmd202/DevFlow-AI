# Contributing to DevFlow AI

Use a feature branch such as `feature/<topic>`, `fix/<topic>`, or `chore/<topic>`. Use Conventional Commits, for example `test: cover an adapter contract`.

## Development setup

On Linux or macOS, run `make dev`, then `.venv/bin/python -m pip install -r requirements/test.txt`. On Windows, run `.\scripts\dev.ps1 -Task dev`, then `.\.venv\Scripts\python.exe -m pip install -r requirements/test.txt`. Use the virtual environment's Python for the checks below.

## Pull request checks

- Run `python -m ruff check . --output-format=github` and `python -m ruff format --check .`.
- Run `python -m mypy --strict src/ tests/`.
- Run `python -m pytest -m "not integration" --cov=src --cov-fail-under=80 --cov-report=term-missing --cov-report=xml --cov-report=html`.
- Run `python -m pytest -m integration` to exercise the temporary SQLite migration round-trip.
- Regenerate the OpenAPI document with `make docs` or `.\scripts\dev.ps1 -Task docs` when the contract changes.

## Add or change an adapter

1. Determine its execution mode from the supported integration mechanism.
2. Define its capability metadata, including supported actions and authentication.
3. Define a typed protocol scoped to those actions. Use an explicit approval gate for CLI handoffs.
4. Implement the offline stub and return typed placeholder data.
5. Register the stub in the adapter registry.
6. Test the capability, health contract, actions, and registry lookup without provider calls.
7. Update the classification table and associated specifications through review.

| Mode | Phase 0 adapters |
| --- | --- |
| `automated_api` | ChatGPT, Claude, Figma, GitHub, Ollama, MCP |
| `cli_handoff` | Codex |
| `manual_handoff` | Kiro, NotebookLM |
| `unknown` | Antigravity, Stitch |
