# RekaKebijakan Backend

The RekaKebijakan backend is a FastAPI API for authentication, document upload, policy simulation workflows, evidence-based reports, and follow-up interactions. Main data is stored in PostgreSQL; source documents are stored locally or in Firebase Storage.

## Run Locally

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python run.py
```

`python run.py` starts Uvicorn on port `5001`.

From the repository root, Docker options are available:

```sh
make up       # backend + PostgreSQL
make full-up  # backend + PostgreSQL + frontend
```

## Configuration

Copy `.env.example` to `.env` to change default values.

Important settings:

- `DATABASE_URL`: PostgreSQL URL using the `psycopg` driver.
- `CORS_ORIGINS`: allowed frontend origins.
- `SESSION_COOKIE_NAME`, `SESSION_TTL_SECONDS`, `SESSION_COOKIE_SECURE`: session cookie settings.
- `STORAGE_BACKEND`: `local` or `firebase`.
- `POLICY_PROVIDER`: `deterministic` or `openai`.

Registration uses email and password, then creates a seven-day session in an HTTP-only cookie. Workflow endpoints can only access projects owned by the signed-in user.

## Storage and Documents

By default, PDF, DOCX, Markdown, and TXT files are stored in `DATA_DIR/uploads`. Extracted text, workflow state, jobs, and evidence metadata are stored in PostgreSQL.

For Firebase Storage, set:

```sh
STORAGE_BACKEND=firebase
FIREBASE_STORAGE_BUCKET=<bucket-name>
GOOGLE_APPLICATION_CREDENTIALS=<service-account-json-path>
```

In Docker Compose, use `FIREBASE_CREDENTIALS_HOST_PATH` so the credential file is mounted into the container.

## Providers and Simulation

`POLICY_PROVIDER=deterministic` generates ontology, graphs, events, reports, interviews, and feedback locally with reproducible output.

For an OpenAI-compatible provider, set `POLICY_PROVIDER=openai`, `LLM_API_KEY`, and optionally `LLM_BASE_URL` or `LLM_MODEL`.

The CAMEL/OASIS runtime is enabled by default and requires `LLM_API_KEY` and `ZEP_API_KEY`. For local mode without external services, set:

```sh
OASIS_ENABLED=false
DEFAULT_SIMULATION_ENGINE=deterministic
```

## Worker and Health Checks

Workflow stages normally enter the job queue. `worker.py` claims jobs from PostgreSQL with leases, heartbeats, retries, and revision checks so processing can recover after a restart.

Public endpoints:

- `GET /health`: check the API process.
- `GET /ready`: check the API and PostgreSQL connection.
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`

## Tests

```sh
.venv/bin/python -m pytest -vv
.venv/bin/python -m compileall -q app
.venv/bin/python -m app.evaluation
```
