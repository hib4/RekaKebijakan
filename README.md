# RekaKebijakan

RekaKebijakan is a policy-scenario simulation prototype with a React frontend and an original FastAPI backend. Its staged workflow covers source intake, graph construction, environment preparation, simulation, progressive reporting, and evidence-aware follow-up.

## Architecture

- `frontend/`: React 19, TypeScript, and Vite user interface.
- `backend/`: FastAPI application factory, Pydantic request validation, SQLite persistence, local document storage, and background jobs served by Uvicorn.

The backend defaults to a deterministic demo engine. It requires no LLM, graph service, queue, or cloud account. Uploaded PDF, DOCX, Markdown, and TXT files are extracted locally, and generated graph, persona, event, risk, report, citation, log, and interaction data remain durable in SQLite.

## Local Run

### One-command Docker

Start the backend with its persistent SQLite database and uploaded-document storage:

```sh
make up
```

Start the full stack instead:

```sh
make full-up
```

The services are available at:

- Frontend: `http://localhost:5173` when using `make full-up`
- Backend API: `http://localhost:5001`
- API documentation: `http://localhost:5001/docs`
- Health check: `http://localhost:5001/health`

Use `make up-d` or `make full-up-d` for detached startup, `make health` to check the services, and `make full-down` to stop them. SQLite, its WAL files, and uploaded documents are retained in the Docker volume `rekakebijakan_backend_data` across shutdowns and image rebuilds.

`make down` and `make full-down` never delete application data. To remove the database and uploaded documents intentionally, run `make reset` and then the displayed confirmation command.

Copy `.env.example` to `.env` to customize host ports, CORS origins, upload limits, job delay, or frontend build variables.

### Local processes

Start the backend:

```sh
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[test]"
python run.py
```

Start the frontend in another terminal:

```sh
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The frontend uses `http://localhost:5001` by default. IDs beginning with `demo-` continue to use the original local browser demo; newly uploaded projects use the FastAPI service. See `frontend/.env.example` to override this behavior.

## Workflow API

1. `POST /api/projects` uploads project metadata and real source files.
2. `POST /api/simulations/<id>/graph-build` constructs the policy graph.
3. `POST /api/simulations/<id>/environment/generate` creates 30 synthetic personas and scenario configuration.
4. `POST /api/simulations/<id>/runs` executes 3, 5, or 8 rounds with pause, resume, cancellation, and event retrieval.
5. `POST /api/simulations/<id>/reports` creates report sections, risks, and evidence references.
6. `POST /api/simulations/<id>/interactions` supports report, persona, evidence, risk, comparison, and revision tools.

The frontend-compatible stage endpoint is `POST /api/simulations/<id>/stages/<stage>/start`. Poll `GET /api/simulations/<id>` for a canonical workflow snapshot.

## Verification

```sh
cd backend
.venv/bin/python -m pytest -vv
.venv/bin/python -m compileall -q app

cd ../frontend
npm run lint
npm run build
```

Backend tests cover deterministic generation, all four document types, SQLite persistence and job recovery, upload validation, round configuration, simulation control, cited reports, all interaction tools, and the complete API workflow.

Authentication uses seven-day opaque server sessions in an HTTP-only cookie. Register at `/register` with name, email, and a password of at least 6 characters. Backend projects and workflow artifacts are private to their creator; legacy unowned rows remain inaccessible.

Containerized verification is also available:

```sh
make test
```
