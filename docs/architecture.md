# Architecture

## System positioning

NovelOps is a front/back separated Agent Team Harness for AI-assisted web-novel production.

The MVP converts Douyin public hotspots into structured web-novel assets:

1. Hotspot extraction.
2. Hotspot normalization.
3. Hit-pattern and novelization analysis.
4. Title and cover-plan generation.
5. Book creation and Agent Team initialization.
6. MiniBible creation.
7. Chapter brief creation.
8. Chapter draft generation.
9. AI review.
10. Human approval, revision, or final lock.

## High-level architecture

```text
Vercel Frontend
  ↓ HTTP API
Local Persistent Backend / Harness
  ↓
Feishu Bitable as the only database
  ↓
External tools: OpenCLI, LLM APIs, optional image APIs
```

## Frontend

- Next.js on Vercel.
- Control and observability only.
- Does not call LLMs, OpenCLI, or Feishu secrets directly.
- Talks only to backend APIs.

Responsibilities:

- Dashboard.
- Pipeline control.
- Agent Team status panel.
- Hotspot pool.
- Analysis approval.
- Title and cover approval.
- Book workspace.
- Chapter review desk.

## Backend

- Local persistent FastAPI service.
- Runs API server and worker loop.
- Owns Agent Team Harness, pipeline orchestration, OpenCLI execution, LLM calls, Feishu repository layer, approval logic, review logic, and revision logic.

Responsibilities:

- API surface for frontend.
- Worker loop.
- StepRun claiming and retry.
- Agent execution.
- Schema validation.
- Feishu read/write.
- OpenCLI invocation.
- LLM invocation.
- Review and revision flow.

## Database

- Feishu Bitable only for v0.1.
- Stores tasks, states, agent memory, artifacts, approvals, versions, review reports, and snapshots.

## Tooling

- OpenCLI for Douyin public hotspot extraction.
- LLM APIs for Agent reasoning and generation.
- Optional image API for cover assets. v0.1 can start with cover prompts only.

## Stability rules

- Every step must be idempotent.
- Every Agent output must pass schema validation.
- Key gates require human approval.
- Failed steps are retryable.
- Chapter drafts are versioned; no overwrite.
- OpenCLI only extracts public Douyin hotspot data.
- Frontend never stores API secrets.

## Backend module layout

```text
app/
  main.py
  api/routes/
  harness/
    orchestrator.py
    worker_loop.py
    step_executor.py
    dependency_resolver.py
    state_machine.py
    approval_gate.py
    retry_policy.py
    lineage.py
    task_claim.py
  agents/
    base.py
    registry.py
    runtime.py
    roles/
  tools/
    opencli_runner.py
    llm_client.py
    image_client.py
  feishu/
    client.py
    table_map.py
    repositories/
  schemas/
  prompts/
opencli-plugin/
  douyin/hotspots.ts
```

## Frontend module layout

```text
app/
  dashboard/
  pipelines/
  agents/
  hotspots/
  analyses/
  title-cover/
  books/[bookId]/
  review/
  settings/
src/
  api/
  components/
  types/
```
