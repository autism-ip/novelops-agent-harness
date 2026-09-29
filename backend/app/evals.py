"""Offline, reproducible fixture comparison; no live model/API credentials."""
from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.generation import CallContext, ChatProvider, Completion, ModelFailure, ModelRouter, Prompt, Route, TraceRecorder, digest


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


def evaluate_live(fixtures: list[dict], route: Route, provider, prompt: Prompt) -> dict:
    """Run the same synthetic constraints through a real provider; keep output text local."""
    if not fixtures:
        raise ValueError("At least one fixture required")
    trace = OfflineTrace()
    router = ModelRouter({"eval":route},{route.provider:provider},trace)
    rows = []
    started = time.monotonic()
    try:
        for fixture in fixtures:
            try:
                output = router.generate("eval",prompt,fixture["input"],SCHEMAS[fixture["kind"]],
                    CallContext(run_id="live-eval",step_id=fixture["id"],workflow_version="live-eval-v1"))
                content = output.model_dump()
                rows.append({"fixture_id":fixture["id"],"kind":fixture["kind"],"schema_pass":True,
                             "findings":violations(content,fixture["expected"]),"output_hash":digest(content),
                             "failure_class":None})
            except ModelFailure as exc:
                rows.append({"fixture_id":fixture["id"],"kind":fixture["kind"],"schema_pass":False,
                             "findings":["schema_failure"] if exc.failure_class == "SchemaFailure" else [],
                             "output_hash":None,"failure_class":exc.failure_class})
    finally:
        router.close()
    return {"evidence":"live-provider-synthetic-fixtures","fixture_hash":digest(fixtures),
            "route_config":route.model_dump(),"route_hash":digest(route.model_dump()),
            "prompt":prompt.model_dump(),"prompt_hash":digest(prompt.model_dump()),
            "workflow_version":"live-eval-v1","fixtures":rows,
            "schema_pass_rate":sum(row["schema_pass"] for row in rows)/len(rows),
            "constraint_violations":sum(len(row["findings"]) for row in rows),
            "usage":trace.usage(run_id="live-eval"),"wall_seconds":round(time.monotonic()-started,3),
            "human_revision_rate":None,
            "limitations":"Synthetic fixtures; no production workflow, human revision or provider invoice observations."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures",type=Path,default=Path(__file__).resolve().parent/"fixtures"/"evals.json")
    parser.add_argument("--output",type=Path)
    parser.add_argument("--live-provider",choices=("openai","deepseek"))
    parser.add_argument("--live-model")
    parser.add_argument("--live-prompt",default="Return JSON grounded in supplied canonical facts.")
    args = parser.parse_args()
    fixtures = json.loads(args.fixtures.read_text())
    if args.live_provider:
        if not args.live_model:
            parser.error("--live-model is required with --live-provider")
        key = os.environ.get(args.live_provider.upper()+"_API_KEY","")
        if not key:
            parser.error(args.live_provider.upper()+"_API_KEY is required for a live evaluation")
        route = Route(provider=args.live_provider,model=args.live_model,max_retries=0,
                      timeout=10,max_output_tokens=512)
        result = evaluate_live(fixtures,route,ChatProvider(args.live_provider,key),
                               Prompt(version="live-eval-v1",template=args.live_prompt))
    else:
        if args.live_model:
            parser.error("--live-provider is required with --live-model")
        result = compare(fixtures)
    report = json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:
        args.output.write_text(report+"\n")
    else:
        print(report)


if __name__ == "__main__":
    main()
