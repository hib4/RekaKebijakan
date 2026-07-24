# Formal evaluation

Fixtures under `fixtures/v1/` are deterministic and contain the source set, required concepts, and a report represented as atomic claims. The evaluator performs no network calls and reports:

- `concept_recall`: required concepts present in report claim text.
- `citation_validity`: citation references that identify a fixture source.
- `citation_coverage`: evidence-requiring claims with at least one valid citation.

Run from `backend/` with `python -m app.evaluation`. The command emits one JSON object and fails when any aggregate metric is below `--fail-threshold` (default `EVALUATION_FAIL_THRESHOLD=0.8`). A fixture file or directory can be supplied with `--fixtures`.
