# RekaKebijakan Backend

FastAPI, Pydantic, PostgreSQL, and local-file implementation of the policy workflow. It uses local email/password accounts.

The backend uses a Python application factory and service-oriented structure tailored to policy simulation. PostgreSQL-backed jobs provide leased, retryable task execution, while the grounded deterministic provider supports local use without mandatory AI services.

From the repository root, `make up` builds and starts PostgreSQL and the API. Use `make full-up` to include the frontend. PostgreSQL data and uploaded documents use separate persistent volumes.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Uploaded PDF, DOCX, Markdown, and text documents are stored below `DATA_DIR/uploads`; extracted text and workflow state are durable in PostgreSQL. Set `JOB_DELAY=0` for fast tests. In-progress jobs recover when the app starts.

Run the automated tests with `pytest`. The suite covers authentication and authorization, all document formats, deterministic generation, durable job recovery, validation, simulation controls, and the complete upload-to-report-to-interaction API workflow.

Frontend aliases use `/api/simulations/<id>/stages/<stage>/start`, `/pause`, `/resume`, and `/interactions`. Canonical project, graph, environment, run/event/control, report/evidence, and interaction resources are also exposed.

`python run.py` starts Uvicorn on port 5001. Keep `workers=1`: workflow execution currently uses process-local worker threads. A multi-worker deployment requires leased database jobs or an external queue even though durable state lives in PostgreSQL.

## Configuration

Copy `.env.example` to `.env` to override defaults. `DATABASE_URL` must be a SQLAlchemy PostgreSQL URL using the psycopg driver. Registration is open and automatically creates a seven-day opaque session in the HTTP-only `rk_session` cookie. `SESSION_COOKIE_NAME`, `SESSION_TTL_SECONDS`, and `SESSION_COOKIE_SECURE` control cookie deployment settings. Set `SESSION_COOKIE_SECURE=true` behind HTTPS.

Compose runs Alembic through a one-shot migration service before the API and worker start. All database timestamps use PostgreSQL `TIMESTAMP WITH TIME ZONE` and application code supplies timezone-aware UTC values. Workflow state and job configuration use `JSONB`.

## Analysis providers

`POLICY_PROVIDER=deterministic` is the default. It derives ontology terms, graph issues, personas, simulation events, reports, interviews, and graph-memory feedback from stored document chunks with reproducible output and structured citations.

Set `POLICY_PROVIDER=openai`, `LLM_API_KEY`, and optionally `LLM_BASE_URL`/`LLM_MODEL` to use an OpenAI-compatible provider for ontology and report generation. Source IDs returned by a model are never trusted; citation provenance is resolved and validated against PostgreSQL document chunks.

Documents are split into deterministic, content-hashed chunks. Graph nodes, report sections, risks, and interaction answers expose structured evidence. Internal storage paths are not returned by project or evidence APIs.

The API only enqueues workflow stages in normal deployments. `worker.py` claims jobs with PostgreSQL `FOR UPDATE SKIP LOCKED`, leases, heartbeats, retries, and stale-revision checks. Tests use the embedded worker for speed.

## Optional integrations

Zep and OASIS are not runtime dependencies. The native PostgreSQL graph, policy-agent simulator, evidence retrieval, interviews, and graph-memory feedback should be evaluated first. Add Zep only if graph retrieval quality or graph scale exceeds PostgreSQL needs. Add OASIS only after policy-domain evaluation demonstrates material quality gains over the native simulator, and after reviewing its operational and licensing impact.

`GET /health` reports process liveness. `GET /ready` also verifies that PostgreSQL accepts queries and is used by the container health check.

`CORS_ORIGINS` must list explicit browser origins; wildcard origins are rejected because credentialed CORS is enabled. Unsafe authenticated browser requests are accepted only from those origins. The defaults allow the local Vite origins. Health endpoints, OpenAPI documentation, and `/api/auth/*` are public; all project, simulation, run, report, and interaction endpoints require authentication and expose only resources owned by the current user.

Auth endpoints are `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, and `POST /api/auth/logout`. Install `.[llm]` only when implementing an OpenAI-compatible provider; the current engine intentionally remains deterministic and offline.

## Test

```sh
.venv/bin/python -m pytest -vv
.venv/bin/python -m compileall -q app
.venv/bin/python -m app.evaluation
```
