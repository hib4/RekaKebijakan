# RekaKebijakan Backend

Flask, Pydantic, SQLite, and local-file implementation of the policy workflow. It is deterministic and needs no credentials or external services.

The structure follows MiroFish's Python application-factory and service-oriented style, but the implementation is original and policy-specific. SQLite-backed jobs replace process-only task state, and the deterministic engine replaces mandatory Zep/OASIS/LLM dependencies for local use.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
flask --app 'app:create_app' run --port 5001
```

Uploaded PDF, DOCX, Markdown, and text documents are stored below `DATA_DIR/uploads`; extracted text and workflow state are durable in SQLite. Set `JOB_DELAY=0` for fast tests. In-progress jobs recover when the app starts.

Run the automated tests with `pytest`. The suite covers all document formats, deterministic generation, durable job recovery, validation, simulation controls, and the complete upload-to-report-to-interaction API workflow.

Frontend aliases use `/api/simulations/<id>/stages/<stage>/start`, `/pause`, `/resume`, and `/interactions`. Canonical project, graph, environment, run/event/control, report/evidence, and interaction resources are also exposed.

## Configuration

Copy `.env.example` to `.env` to override defaults. No variable is required in demo mode. Install `.[llm]` only when implementing an OpenAI-compatible provider; the current engine intentionally remains deterministic and offline.

## Test

```sh
.venv/bin/python -m pytest -vv
.venv/bin/python -m compileall -q app
```
