import json
from pathlib import Path

from app.evals import FixtureProvider, compare, evaluate_live
from app.generation import Prompt, Route, digest


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


def test_live_evaluation_reuses_fixtures_without_exposing_response_text():
    fixtures = json.loads((Path(__file__).parents[1]/"app"/"fixtures"/"evals.json").read_text())
    route = Route(provider="deepseek",model="fixture-model",max_retries=0)
    class ByStepProvider:
        def complete(self, route, messages):
            data = json.loads(messages[1]["content"])
            fixture = next(f for f in fixtures if f["input"] == data)
            return FixtureProvider(fixture,"candidate").complete(route,messages)

    report = evaluate_live(fixtures,route,ByStepProvider(),Prompt(version="test-v1",template="Return JSON."))
    assert report["evidence"] == "live-provider-synthetic-fixtures"
    assert report["fixture_hash"] == digest(fixtures)
    assert report["schema_pass_rate"] == 1
    assert report["constraint_violations"] == 0
    assert report["usage"]["attempts"] == 6
    assert report["usage"]["estimated_cost"] is None
    assert report["human_revision_rate"] is None
    assert all(row["output_hash"] and "output" not in row for row in report["fixtures"])
