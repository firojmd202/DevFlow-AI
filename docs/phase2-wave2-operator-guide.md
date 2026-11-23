# DevFlow AI — Wave 2 operator guide

## Local setup

Use Python 3.12 or later and install the repository package and development requirements. Point `DATABASE_URL` at a disposable SQLite file for development and verification. Set the database URL before running Alembic and before launching the API. Migration 009 follows 008 and adds seven specification tables, keeping existing Phase 1 and Wave 1 tables intact. Back up a database before any migration. Downgrading 009 removes the specification tables and their data. Exercise that path on a separate copy.

On Windows from the repository root:

```powershell
$env:DATABASE_URL = 'sqlite+aiosqlite:///./devflow-wave2-local.db'
.venv/Scripts/python.exe -m alembic heads
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m uvicorn devflow_api.main:app --host 127.0.0.1
```

In a second shell, set `DEVFLOW_API_BASE_URL` if it differs from the local default and run `.venv/Scripts/python.exe -m streamlit run src/devflow_ui/app.py`. Keep the API on a trusted local interface. The configured local operator ID represents the human decision maker in this deployment model.

## Providers and context

Ollama is the default. Start Ollama locally, install a model such as `ollama pull llama3.2` and set `OLLAMA_MODEL` to that name. The default `OLLAMA_BASE_URL` is `http://localhost:11434`. Use the provider display to check whether the local service is available. Timeouts and retries use the `AI_REQUEST_TIMEOUT_SECONDS`, `AI_MAX_RETRIES` and `AI_RETRY_BUDGET_SECONDS` settings.

For optional OpenAI usage, explicitly set `AI_PROVIDER=openai`, supply `OPENAI_API_KEY` through local secret configuration and choose `OPENAI_MODEL`. Use cloud inference only for data you have cleared for that provider. The application uses the explicitly configured provider and Ollama failures do not start cloud requests.

Leave `MCP_SERVERS_CONFIG` empty unless an operator has approved a local server. If enabled, provide a JSON array of server configurations. Set each enabled server's name, command argument vector, explicit tool list, read-only classification and input schema. Use minimal explicit environment entries and enable `MCP_STRICT_SCHEMA_VALIDATION` to require a registered schema. Approve invocations according to the adapter policy. A configured server executable runs locally with operator-level access, so allowlists and environment isolation complement host permissions. Treat tool output and repository text as untrusted input. Required context failure stops generation and optional failures may allow it to continue.

## Specification lifecycle

1. Use **Specification management** in Streamlit to enter the feature details, acceptance criteria and available context. Submit the request, select the configured provider/model and start generation.
2. Poll generation status and inspect the requirements, design and tasks artifacts. Use cancellation for active work. A failed attempt can be retried from the draft after resolving the cause.
3. Start review on the generated version. Read the deterministic and AI-assisted findings with their evidence and severity. Evaluate recommendations independently. Address blocking findings through a revision, regenerate as needed and compare versions before submitting another review.
4. Request approval for the current reviewed version and digest. Record the human decision via the approval view. For standalone approval, consumption and the version transition commit together. For workflow-bound approval, Wave 1 records the decision and the specification service validates and finalizes the artifact binding. Protected dispatch performs its own authorization transaction, and a subsequent implementation step retains its separate human gate.

Startup requires migration 009 and settles Wave 1 recovery before specification recovery. Pending and running specification attempts become failed with `INTERRUPTED`. The current interrupted generation returns to draft and the current interrupted review returns to generated. Recovery records standalone expiry once without changing the approval record. Retry work explicitly after a restart. When a workflow-bound decision committed before specification finalization, request a fresh decision for the still-eligible version and review its digest. The previous decision alone cannot authorize dispatch.

## API inventory

The prefix is `/api/v1/specification-requests`.

| Operation | Routes relative to prefix |
|---|---|
| Configured providers | `GET /providers` |
| Requests | `GET /`, `POST /`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}` |
| Generation and review | `POST /{id}/generate`, `DELETE /{id}/generate`, `POST /{id}/review`, `DELETE /{id}/review`, `GET /{id}/status` |
| Revisions and artifacts | `POST /{id}/revision`, `GET /{id}/versions`, `GET /{id}/versions/{version_id}/artifacts/{artifact_type}` |
| Findings | `GET /{id}/review/findings`, `POST /{id}/findings/{finding_id}/acknowledge` |
| Approval and audit | `POST /{id}/approval`, `POST /{id}/approve`, `GET /{id}/audit` |

Generation and review submission returns HTTP 202. Status retrieval returns HTTP 200 and reports the attempt state. A failed attempt carries its diagnostic code in `error_code`. A cancellation request accepted with HTTP 200 reports `cancellation_requested`. Poll until the attempt reaches `cancelled` with `PROVIDER_CANCELLED`. A cancellation request for an absent or terminal current attempt returns HTTP 409 with `TASK_NOT_CANCELLABLE`. For synchronous errors, read `code` from the error response.

With v1.6.1 the owner approved this asynchronous contract and the existing error envelope. For MCP context, send `mcp_contexts` with `POST /{id}/generate` or in a workflow generator step's inputs. Each item has `server`, `tool`, `arguments` and `required`. Use a configured read-only tool and schema-valid arguments. Required failures produce `MCP_CONTEXT_FAILURE` and optional failures leave an audit entry and allow reduced-context generation. These plans do not replay during startup. Streamlit supports normal generation and repository context text. [Generated OpenAPI contract](openapi.json) [Current verification](reports/phase2-wave2-final-compliance-verification.md)

## Troubleshooting and verification

- For provider unavailability, check the local Ollama address and model installation. A configured cloud key does not change the Ollama retry behavior.
- For MCP failures, check enablement, allowlists, classification, the input schema and the explicit approval. Avoid placing credentials in tool arguments or feature text.
- For stale digests or expired approvals, refresh the current version, review the artifacts and request a fresh approval when eligible. A digest mismatch or inconsistent stored artifact requires investigation before requesting approval again.
- FastAPI startup returns an explicit migration prerequisite if the required schema is absent. Confirm `alembic heads` and use an isolated database for upgrade/downgrade checks.
- Run `.venv/Scripts/python.exe -m pytest tests/ -k wave2 --no-cov` for focused tests, then run the full offline suite with `--cov-branch`. These tests use deterministic provider, subprocess and network fakes.
- Run one API process against the local database. Specification attempts use durable state and fencing, while the process owns active in-memory jobs. The supported workflow stops at approved specifications and gated workflow progression. Wave 2 has no Codex or Kiro execution and does not create GitHub PRs automatically.

See the [Wave 2 final implementation report](reports/phase2-wave2-final-implementation-report.md) for gate results and known gaps.
