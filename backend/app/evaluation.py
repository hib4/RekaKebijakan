"""Deterministic, network-free quality evaluation for policy reports."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


EVALUATOR_VERSION = "1.0.0"
DEFAULT_FIXTURES = Path(__file__).resolve().parents[2] / "evaluations" / "fixtures" / "v1"


def _normalized(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold(), flags=re.UNICODE))


def evaluate_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    if fixture.get("schema_version") != "1.0":
        raise ValueError(f"unsupported fixture schema version: {fixture.get('schema_version')}")
    required = fixture["expected"]["required_concepts"]
    claims = fixture["output"]["claims"]
    source_ids = {source["id"] for source in fixture["sources"]}
    output_text = _normalized(" ".join(claim["text"] for claim in claims))

    found = [concept for concept in required if _normalized(concept) in output_text]
    references = [citation for claim in claims for citation in claim.get("citations", [])]
    valid_references = [citation for citation in references if citation in source_ids]
    grounded_claims = [claim for claim in claims if claim.get("requires_citation", True)]
    covered_claims = [
        claim
        for claim in grounded_claims
        if any(citation in source_ids for citation in claim.get("citations", []))
    ]

    metrics = {
        "concept_recall": len(found) / len(required) if required else 1.0,
        "citation_validity": len(valid_references) / len(references) if references else 1.0,
        "citation_coverage": len(covered_claims) / len(grounded_claims) if grounded_claims else 1.0,
    }
    return {
        "id": fixture["id"],
        "schema_version": fixture["schema_version"],
        "metrics": metrics,
        "counts": {
            "required_concepts": len(required),
            "concepts_found": len(found),
            "citations": len(references),
            "valid_citations": len(valid_references),
            "claims_requiring_citation": len(grounded_claims),
            "claims_covered": len(covered_claims),
        },
    }


def run(fixtures_path: Path, threshold: float) -> dict[str, Any]:
    if not 0 <= threshold <= 1:
        raise ValueError("fail threshold must be between 0 and 1")
    paths = sorted(fixtures_path.glob("*.json")) if fixtures_path.is_dir() else [fixtures_path]
    if not paths or not all(path.is_file() for path in paths):
        raise ValueError(f"no evaluation fixtures found at {fixtures_path}")

    fixtures = [evaluate_fixture(json.loads(path.read_text(encoding="utf-8"))) for path in paths]
    metric_names = ("concept_recall", "citation_validity", "citation_coverage")
    aggregate = {
        name: sum(fixture["metrics"][name] for fixture in fixtures) / len(fixtures)
        for name in metric_names
    }
    passed = all(value >= threshold for value in aggregate.values())
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "fixture_set": str(fixtures_path),
        "threshold": threshold,
        "passed": passed,
        "metrics": aggregate,
        "fixtures": fixtures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument(
        "--fail-threshold",
        type=float,
        default=float(os.environ.get("EVALUATION_FAIL_THRESHOLD", "0.8")),
    )
    args = parser.parse_args(argv)
    try:
        result = run(args.fixtures, args.fail_threshold)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"evaluator_version": EVALUATOR_VERSION, "passed": False, "error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
