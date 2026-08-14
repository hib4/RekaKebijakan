# RekaKebijakan

RekaKebijakan is a public policy scenario simulation prototype. It uses a React frontend and a FastAPI backend to manage source documents, build policy graphs, run simulations, generate reports, and answer evidence-based follow-up questions.

## Structure

- `frontend/`: React, TypeScript, and Vite interface.
- `backend/`: FastAPI API, PostgreSQL, authentication, document storage, worker, and simulation engine.
- `evaluations/`: deterministic test data and evaluator for report quality checks.

## Run with Docker

Start the backend and PostgreSQL:

```sh
make up
```

Start the backend, PostgreSQL, and frontend:

```sh
make full-up
```

Local services:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:5001`
- API docs: `http://localhost:5001/docs`
- API health check: `http://localhost:5001/health`

Common commands:

```sh
make up-d        # run backend in the background
make full-up-d   # run the full stack in the background
make health      # check services
make full-down   # stop the full stack without deleting data
make reset       # show instructions for deleting persistent data
```

PostgreSQL data and uploaded documents are stored in Docker volumes. `make down` and `make full-down` do not delete data.

## Run Locally

Backend:

```sh
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[test]"
python run.py
```

Frontend:

```sh
cd frontend
bun install
bun run dev
```

Open `http://localhost:5173`. The frontend uses `/backend` as the default API path; during development, Vite proxies it to FastAPI at `http://localhost:5001`.

## Configuration

Copy `.env.example` to `.env` if you need to change ports, CORS, upload limits, storage, LLM provider, or frontend settings.

The default simulation mode uses CAMEL/OASIS and requires `LLM_API_KEY` and `ZEP_API_KEY`. For a local mode without external services, set:

```sh
OASIS_ENABLED=false
DEFAULT_SIMULATION_ENGINE=deterministic
```

For Firebase Storage, set `STORAGE_BACKEND=firebase`, `FIREBASE_STORAGE_BUCKET`, and `FIREBASE_CREDENTIALS_HOST_PATH`. The `secrets/` directory is ignored by Git.

## Verification

Backend:

```sh
cd backend
.venv/bin/python -m pytest -vv
.venv/bin/python -m compileall -q app
```

Frontend:

```sh
cd frontend
bun run lint
bun run build
```

Containers and evaluation:

```sh
make test
make evaluation
make smoke
```

`make evaluation` runs the deterministic network-free evaluation. `make smoke` tests a running production full stack.
