"""Real eval CLI/router/provider contracts with only outbound HTTP controlled.

These tests verify evaluator behavior and resource handling, not live-model quality.
"""
import json
import runpy
import sys
from pathlib import Path

import httpx
import pytest

from app.generation import ChatProvider, Prompt, Route, digest

EVAL_PROGRAM = Path(__file__).parents[1] / "app" / "evals.py"
REAL_CLIENT = httpx.Client
PRIVATE_PROSE = "PRIVATE_GENERATED_PROSE_FOR_EVAL_BOUNDARY_ONLY"
SYNTHETIC_KEY = "synthetic-eval-credential"


def invoke(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["app.evals", *map(str, args)])
    runpy.run_path(str(EVAL_PROGRAM), run_name="__main__")


def fixture_file(tmp_path, content=None):
    fixtures = content if content is not None else [{"id": "rewrite-one", "kind": "rewrite",
        "input": {"constraint": "Preserve the paid secret"},
        "expected": {"must_include": [PRIVATE_PROSE]}}]
    path = tmp_path / "fixtures.json"
    path.write_text(json.dumps(fixtures), encoding="utf-8")
    return path


def install_transport(monkeypatch, respond):
    requests, clients = [], []

    def handler(request):
        requests.append(request)
        return respond(request)

    def client_factory(*args, **kwargs):
        assert "transport" not in kwargs
        client = REAL_CLIENT(*args, transport=httpx.MockTransport(handler), **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(httpx, "Client", client_factory)
    return requests, clients


def completion(content=None, finish="stop"):
    return {"model": "actual-response-model", "choices": [{"finish_reason": finish,
        "message": {"content": json.dumps(content if content is not None else {"content": PRIVATE_PROSE})}}],
        "usage": {"prompt_tokens": 47, "completion_tokens": 17}}


def test_default_offline_cli_reports_golden_fixture_limits(monkeypatch, capsys):
    invoke(monkeypatch)
    result = json.loads(capsys.readouterr().out)
    assert result["evidence"] == "mocked-provider-fixtures"
    assert "synthetic fixture rates" in result["pricing"]
    baseline, candidate = result["variants"]
    assert len(baseline["fixtures"]) == len(candidate["fixtures"]) == 6
    assert baseline["schema_pass_rate"] < candidate["schema_pass_rate"] == 1
    assert baseline["constraint_violations"] > candidate["constraint_violations"] == 0
    assert all(variant["human_revision_rate"] is None for variant in result["variants"])
    assert all(variant["usage"]["attempts"] == 6 for variant in result["variants"])
    assert "no live model quality/cost" in result["limitations"]


def test_offline_custom_fixtures_write_constraint_failures_without_prose(tmp_path, monkeypatch, capsys):
    fixtures = [
        {"id": "signal", "kind": "opportunity", "input": {}, "expected": {"must_include": ["Original signal"]},
         "baseline": {"summary": "", "genres": ["mystery"], "risk_level": "low"},
         "candidate": {"summary": "Original signal", "genres": ["mystery"], "risk_level": "low"}},
        {"id": "chapter", "kind": "chapter", "input": {},
         "expected": {"must_include": ["paid"], "must_exclude": ["Unsafe"], "facts": {"cost": "secret"}},
         "baseline": {"content": "Unsafe rescue", "facts": {"cost": "free"}},
         "candidate": {"content": "The rescue is paid", "facts": {"cost": "secret"}}},
        {"id": "continuity", "kind": "continuity", "input": {},
         "expected": {"violations": ["missing ledger rule"]},
         "baseline": {"violations": []}, "candidate": {"violations": ["missing ledger rule"]}},
    ]
    path = fixture_file(tmp_path, fixtures)
    output = tmp_path / "report.json"
    invoke(monkeypatch, "--fixtures", path, "--output", output)
    assert capsys.readouterr().out == ""
    text = output.read_text()
    assert text.endswith("\n")
    report = json.loads(text)
    assert report["fixture_hash"] == digest(fixtures)
    baseline, candidate = report["variants"]
    assert baseline["schema_pass_rate"] == pytest.approx(2 / 3)
    assert baseline["constraint_violations"] == 5
    assert baseline["revision_recommended_rate"] == 1
    assert baseline["fixtures"][1]["findings"] == ["missing_required_text", "forbidden_text", "canonical_fact_mismatch"]
    assert baseline["fixtures"][2]["findings"] == ["continuity_detection_mismatch"]
    assert candidate["schema_pass_rate"] == 1 and candidate["constraint_violations"] == 0
    assert candidate["usage"]["input_tokens"] == 300 and candidate["usage"]["output_tokens"] == 150
    assert candidate["usage"]["estimated_cost"] == pytest.approx(0.0006)
    assert "Unsafe rescue" not in text and "The rescue is paid" not in text


@pytest.mark.parametrize("flags, expected", [
    (["--live-provider", "deepseek"], "--live-model is required"),
    (["--live-model", "model"], "--live-provider is required"),
    (["--live-provider", "deepseek", "--live-model", "model"], "DEEPSEEK_API_KEY is required"),
])
def test_invalid_live_configuration_never_constructs_a_client(tmp_path, monkeypatch, capsys, flags, expected):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    requests, clients = install_transport(monkeypatch, lambda request: httpx.Response(500))
    output = tmp_path / "report.json"
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--fixtures", fixture_file(tmp_path), "--output", output, *flags)
    assert error.value.code == 2
    assert expected in capsys.readouterr().err
    assert not output.exists() and not requests and not clients


@pytest.mark.parametrize("provider", ["openai", "deepseek"])
def test_live_cli_forwards_bounded_route_and_closes_real_provider(tmp_path, monkeypatch, capsys, provider):
    monkeypatch.setenv(provider.upper() + "_API_KEY", SYNTHETIC_KEY)
    requests, clients = install_transport(monkeypatch, lambda request: httpx.Response(200, json=completion()))
    args = ["--fixtures", fixture_file(tmp_path), "--live-provider", provider, "--live-model", "requested-model",
        "--live-timeout", "12", "--live-max-output-tokens", "777", "--live-prompt", "Preserve the paid secret."]
    if provider == "deepseek":
        args += ["--live-deepseek-thinking", "enabled"]
    invoke(monkeypatch, *args)
    text = capsys.readouterr().out
    report = json.loads(text)
    assert len(requests) == len(clients) == 1 and clients[0].is_closed
    request = requests[0]
    body = json.loads(request.content)
    assert str(request.url) == ChatProvider.URLS[provider]
    assert request.headers["authorization"] == "Bearer " + SYNTHETIC_KEY
    assert request.extensions["timeout"]["read"] == 12
    assert body["model"] == "requested-model" and body["response_format"] == {"type": "json_object"}
    assert body["max_tokens" if provider == "deepseek" else "max_completion_tokens"] == 777
    if provider == "deepseek":
        assert body["thinking"] == {"type": "enabled"}
    else:
        assert "thinking" not in body and "max_tokens" not in body
    assert report["prompt"]["template"] == "Preserve the paid secret."
    assert report["route_config"]["max_retries"] == 0
    assert report["schema_pass_rate"] == 1 and report["constraint_violations"] == 0
    assert report["fixtures"][0]["output_hash"] == digest({"content": PRIVATE_PROSE})
    assert report["usage"]["input_tokens"] == 47 and report["usage"]["output_tokens"] == 17
    assert report["usage"]["estimated_cost"] is None and report["human_revision_rate"] is None
    assert PRIVATE_PROSE not in text and SYNTHETIC_KEY not in text


@pytest.mark.parametrize("failure, expected", [
    ("schema", "SchemaFailure"), ("truncated", "TruncatedOutput"), ("malformed", "MalformedResponse"),
    ("timeout", "Timeout"), ("limited", "RateLimited"),
])
def test_live_cli_keeps_failure_classes_and_usage_honest(tmp_path, monkeypatch, capsys, failure, expected):
    monkeypatch.setenv("DEEPSEEK_API_KEY", SYNTHETIC_KEY)

    def respond(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        if failure == "limited":
            return httpx.Response(429, json={"error": {"message": PRIVATE_PROSE}})
        if failure == "malformed":
            return httpx.Response(200, text="not json")
        return httpx.Response(200, json=completion({"unexpected": PRIVATE_PROSE}) if failure == "schema"
            else completion(finish="length"))

    requests, clients = install_transport(monkeypatch, respond)
    invoke(monkeypatch, "--fixtures", fixture_file(tmp_path), "--live-provider", "deepseek", "--live-model", "model")
    text = capsys.readouterr().out
    report = json.loads(text)
    row = report["fixtures"][0]
    assert row["failure_class"] == expected and row["schema_pass"] is False and row["output_hash"] is None
    assert row["findings"] == (["schema_failure"] if failure == "schema" else [])
    assert len(requests) == len(clients) == report["usage"]["attempts"] == 1
    assert clients[0].is_closed and report["usage"]["retries"] == 0
    assert report["usage"]["estimated_cost"] is None
    assert report["usage"]["input_tokens"] == (47 if failure in {"schema", "truncated"} else None)
    assert report["usage"]["unknown_usage_attempts"] == (0 if failure in {"schema", "truncated"} else 1)
    assert PRIVATE_PROSE not in text and SYNTHETIC_KEY not in text


@pytest.mark.parametrize("fixtures", [[], {"not": "a fixture array"}])
def test_invalid_fixture_container_is_rejected_before_live_client_creation(tmp_path, monkeypatch, capsys, fixtures):
    monkeypatch.setenv("DEEPSEEK_API_KEY", SYNTHETIC_KEY)
    requests, clients = install_transport(monkeypatch, lambda request: httpx.Response(200, json=completion()))
    output = tmp_path / "report.json"
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--fixtures", fixture_file(tmp_path, fixtures), "--output", output,
            "--live-provider", "deepseek", "--live-model", "model")
    assert error.value.code == 2
    assert "non-empty JSON array" in capsys.readouterr().err
    assert not requests and not clients and not output.exists()


def test_empty_function_inputs_raise_before_requests_and_preserve_caller_client():
    from app.evals import compare, evaluate_live
    requests = []
    with pytest.raises(ValueError, match="At least one fixture required"):
        compare([])
    with REAL_CLIENT(transport=httpx.MockTransport(lambda request: requests.append(request))) as client:
        provider = ChatProvider("deepseek", SYNTHETIC_KEY, client=client)
        with pytest.raises(ValueError, match="At least one fixture required"):
            evaluate_live([], Route(provider="deepseek", model="model", max_retries=0), provider,
                Prompt(version="empty-v1", template="Return JSON."))
        assert not requests and not client.is_closed
    assert client.is_closed


def test_eval_usage_filters_runs_and_chapters_without_double_counting():
    from app.evals import OfflineTrace
    trace = OfflineTrace()
    ids = []
    for run, chapter, inputs, outputs, cost, attempt in [
        ("A", "one", 7, 3, 0.01, 0), ("A", "two", 11, 5, 0.02, 1), ("B", "two", 19, 17, 0.04, 0),
    ]:
        identity = trace.start({"kind": "model", "run_id": run, "chapter_id": chapter, "attempt": attempt})
        ids.append(identity)
        trace.finish(identity, status="success", input_tokens=inputs, output_tokens=outputs,
            estimated_cost=cost, latency_ms=10)
    assert len(set(ids)) == 3
    assert [row["trace_id"] for row in trace.list(run_id="A", chapter_id="one")] == ids[:1]
    assert [row["trace_id"] for row in trace.list(chapter_id="two")] == ids[1:]
    assert trace.list(run_id="missing") == []
    run = trace.usage(run_id="A")
    assert run["attempts"] == 2 and run["input_tokens"] == 18 and run["output_tokens"] == 8
    assert run["estimated_cost"] == pytest.approx(0.03) and run["retries"] == 1
    chapter = trace.usage(chapter_id="two")
    assert chapter["input_tokens"] == 30 and chapter["output_tokens"] == 22
    assert chapter["estimated_cost"] == pytest.approx(0.06)
