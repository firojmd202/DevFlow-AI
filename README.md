# DevFlow-AI
## Project goals

DevFlow AI is a local-first development and learning orchestrator. Phase 0 establishes its application structure, offline adapter contracts, and testing workflow.

## Architecture

```text
Streamlit UI  -->  FastAPI backend  -->  SQLite
                       |
                       +--> Offline integration adapters
```

The UI connects through the HTTP API. The API owns database access and migrations. See the [architecture design](.kiro/specs/foundation-and-architecture/design.md).

## Prerequisites

- Python 3.12 or newer
- Docker with the Compose v2 plugin for container use
- Make on Linux or macOS, or PowerShell 7+ on Windows

## Quick start

On Linux or macOS:

```sh
make dev
.venv/bin/python -m pip install -r requirements/test.txt
make test
docker compose up --build -d
docker compose exec devflow-api alembic upgrade head
```

On Windows:

```powershell
.\scripts\dev.ps1 -Task dev
.\.venv\Scripts\python.exe -m pip install -r requirements/test.txt
.\scripts\dev.ps1 -Task test
.\scripts\dev.ps1 -Task up
docker compose exec devflow-api alembic upgrade head
```

Open the UI at `http://127.0.0.1:8501` or the API docs at `http://127.0.0.1:8000/docs`. For local settings, copy `.env.example` to `.env` and replace only the values you need. The containers can start without a dotenv file or provider credentials.

## Project references

- [Requirements](.kiro/specs/foundation-and-architecture/requirements.md)
- [Design](.kiro/specs/foundation-and-architecture/design.md)
- [Implementation tasks](.kiro/specs/foundation-and-architecture/tasks.md)
- [Contributing](CONTRIBUTING.md)
