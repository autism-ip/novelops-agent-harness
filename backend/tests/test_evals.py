import json
from pathlib import Path

from app.evals import compare


def test_same_fixtures_compare_variants_with_honest_metrics():
    fixtures = json.loads((Path(__file__).parents[1]/"app"/"fixtures"/"evals.json").read_text())
    report = compare(fixtures)
    baseline, candidate = report["variants"]
    assert report["evidence"] == "mocked-provider-fixtures"
    assert len(baseline["fixtures"]) == len(candidate["fixtures"]) == 6
    assert baseline["schema_pass_rate"] < candidate["schema_pass_rate"] == 1
    assert baseline["constraint_violations"] > candidate["constraint_violations"] == 0
    assert baseline["human_revision_rate"] is None
    assert candidate["usage"]["attempts"] == 6
    assert candidate["usage"]["estimated_cost"] > 0
    assert baseline["route_hash"] != candidate["route_hash"]
