import json

from app.evaluation import DEFAULT_FIXTURES, evaluate_fixture, main, run


def test_versioned_fixture_is_deterministic_and_passes():
    first = run(DEFAULT_FIXTURES, 1.0)
    second = run(DEFAULT_FIXTURES, 1.0)

    assert first == second
    assert first["passed"] is True
    assert first["metrics"] == {
        "concept_recall": 1.0,
        "citation_validity": 1.0,
        "citation_coverage": 1.0,
    }


def test_metrics_count_invalid_and_uncovered_citations():
    result = evaluate_fixture({
        "schema_version": "1.0",
        "id": "partial",
        "expected": {"required_concepts": ["public access", "monthly review"]},
        "sources": [{"id": "source-1", "text": "Evidence"}],
        "output": {"claims": [
            {"text": "Public access improves.", "citations": ["source-1"]},
            {"text": "Annual review follows.", "citations": ["missing"]},
        ]},
    })

    assert result["metrics"] == {
        "concept_recall": 0.5,
        "citation_validity": 0.5,
        "citation_coverage": 0.5,
    }


def test_cli_emits_json_and_enforces_threshold(tmp_path, capsys):
    fixture = tmp_path / "failing.json"
    fixture.write_text(json.dumps({
        "schema_version": "1.0",
        "id": "failing",
        "expected": {"required_concepts": ["missing concept"]},
        "sources": [{"id": "source-1", "text": "Evidence"}],
        "output": {"claims": [{"text": "Different output", "citations": []}]},
    }), encoding="utf-8")

    assert main(["--fixtures", str(fixture), "--fail-threshold", "0.8"]) == 1
    assert json.loads(capsys.readouterr().out)["passed"] is False
