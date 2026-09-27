"""Offline, reproducible fixture comparison; no live model/API credentials."""
from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.generation import CallContext, Completion, ModelFailure, ModelRouter, Prompt, Route, TraceRecorder, digest


class StrictOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Opportunity(StrictOutput):
    summary: str = Field(min_length=1)
    genres: list[str] = Field(min_length=1)
    risk_level: Literal["low", "medium", "high"]


class StoryBible(StrictOutput):
    premise: str = Field(min_length=1)
    facts: dict[str, str]


class ChapterBrief(StrictOutput):
    goal: str = Field(min_length=1)
    facts: dict[str, str]


class Chapter(StrictOutput):
    content: str = Field(min_length=1)
    facts: dict[str, str]


class Continuity(StrictOutput):
    violations: list[str]


class Rewrite(StrictOutput):
    content: str = Field(min_length=1)


SCHEMAS = {"opportunity":Opportunity,"story_bible":StoryBible,"chapter_brief":ChapterBrief,
           "chapter":Chapter,"continuity":Continuity,"rewrite":Rewrite}


class OfflineTrace(TraceRecorder):
    """In-memory telemetry sink for offline evaluations only."""
    def __init__(self):
        self.rows = []

    def start(self, data):
        trace_id = uuid.uuid4().hex
        self.rows.append({**data,"trace_id":trace_id,"created_at":str(time.time_ns())})
        return trace_id

    def finish(self, trace_id, **fields):
        next(row for row in self.rows if row["trace_id"] == trace_id).update(fields)

    def list(self, *, run_id="", chapter_id=""):
        return [r for r in self.rows if (not run_id or r["run_id"] == run_id)
                and (not chapter_id or r["chapter_id"] == chapter_id)]


class FixtureProvider:
    def __init__(self, fixture, variant):
        self.fixture = fixture
        self.variant = variant

    def complete(self, route, messages):
        return Completion(json.dumps(self.fixture[self.variant],ensure_ascii=False), route.model, 100, 50)


def violations(output: dict, expected: dict) -> list[str]:
    issues = []
    text = json.dumps(output,ensure_ascii=False)
    for required in expected.get("must_include", []):
        if required not in text:
            issues.append("missing_required_text")
    for banned in expected.get("must_exclude", []):
        if banned in text:
            issues.append("forbidden_text")
    for key, value in expected.get("facts", {}).items():
        if output.get("facts", {}).get(key) != value:
            issues.append("canonical_fact_mismatch")
    if "violations" in expected and output.get("violations") != expected["violations"]:
        issues.append("continuity_detection_mismatch")
    return issues


def compare(fixtures: list[dict]) -> dict:
    if not fixtures:
        raise ValueError("At least one fixture required")
    results = []
    for name, provider_name in (("baseline","openai"),("candidate","deepseek")):
        trace = OfflineTrace()
        config = Route(provider=provider_name,model="fixture-model",max_retries=0,
                       input_cost_per_million=1,output_cost_per_million=2)
        prompt = Prompt(version=name+"-v1",template="Return JSON grounded in supplied canonical facts.")
        rows = []
        for fixture in fixtures:
            router = ModelRouter({"eval":config},{provider_name:FixtureProvider(fixture,name)},trace)
            schema_pass = True
            try:
                output = router.generate("eval",prompt,fixture["input"],SCHEMAS[fixture["kind"]],
                    CallContext(run_id=name,step_id=fixture["id"],workflow_version="eval-v1"))
                findings = violations(output.model_dump(),fixture["expected"])
            except ModelFailure:
                schema_pass = False
                findings = ["schema_failure"]
            rows.append({"fixture_id":fixture["id"],"schema_pass":schema_pass,"findings":findings})
        results.append({"variant":name,"route_config":config.model_dump(),"route_hash":digest(config.model_dump()),
            "prompt":prompt.model_dump(),"workflow_version":"eval-v1","fixtures":rows,
            "schema_pass_rate":sum(r["schema_pass"] for r in rows)/len(rows),
            "constraint_violations":sum(len(r["findings"]) for r in rows),
            "revision_recommended_rate":sum(bool(r["findings"]) for r in rows)/len(rows),
            "human_revision_rate":None,"usage":trace.usage(run_id=name),
            "retry_rate":trace.usage(run_id=name)["retries"]/max(trace.usage(run_id=name)["attempts"],1)})
    return {"evidence":"mocked-provider-fixtures", "fixture_hash":digest(fixtures),
            "pricing":"synthetic fixture rates; not provider prices", "variants":results,
            "limitations":"Harness regression evidence only; no live model quality/cost or human revision observations."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures",type=Path,default=Path(__file__).resolve().parent/"fixtures"/"evals.json")
    parser.add_argument("--output",type=Path)
    args = parser.parse_args()
    report = json.dumps(compare(json.loads(args.fixtures.read_text())),ensure_ascii=False,indent=2)
    if args.output:
        args.output.write_text(report+"\n")
    else:
        print(report)


if __name__ == "__main__":
    main()
