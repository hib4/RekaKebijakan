# Formal Evaluation

This folder contains deterministic test data for checking RekaKebijakan report quality without network calls.

Data under `fixtures/v1/` includes:

- source files,
- required concepts,
- a report represented as atomic claims.

The evaluator reports:

- `concept_recall`: required concepts found in report claim text.
- `citation_validity`: citations that reference a valid fixture source.
- `citation_coverage`: evidence-requiring claims with at least one valid citation.

Run from the `backend/` folder:

```sh
python -m app.evaluation
```

The command emits one JSON object and fails if any aggregate metric is below `--fail-threshold`. The default threshold comes from `EVALUATION_FAIL_THRESHOLD` or `0.8`.

A specific test data file or directory can be passed with `--fixtures`.
