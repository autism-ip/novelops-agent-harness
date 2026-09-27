# NovelOps Agent Harness

NovelOps is a Feishu-first, local-first modular harness for cost-efficient AI-assisted web-novel production.

## v0.2 product goal

Build a personal-use-first production system that turns public research signals into versioned story assets and reviewed chapters while keeping infrastructure, model cost, and maintenance overhead low.

The product is workflow/content-centric rather than Agent-centric. The Harness controls execution deterministically; LLM Agents are used only for tasks that genuinely require semantic reasoning or generation.

## Architecture

```text
Next.js / Vercel product UI
  ↓ HTTP / SSE
Local FastAPI modular monolith
  ↓
Harness Kernel
  ├─ Workflow Engine / State Machine
  ├─ Single Scheduler / Single Writer
  ├─ Context Builder
  ├─ Validation / Verification
  ├─ Retry / Recovery / Reconciliation
  ├─ Approval
  └─ Trace / Usage / Cost
  ↓
Provider layer
  ├─ Models: DeepSeek / OpenAI / future providers
  ├─ Tools: OpenCLI / web / APIs / image tools
  └─ Storage: Feishu Base / Docs / Drive
```

## Core design principles

- **Feishu-first:** Feishu Base is the primary structured SSOT for v0.2. Docs, Drive, Workflow, `lark-cli`, and official MCP are used where they provide leverage.
- **Local-first modular monolith:** one FastAPI backend, one authoritative scheduler, one machine writer. No distributed infrastructure until usage proves it is needed.
- **Deterministic Harness:** orchestration, validation, approvals, state transitions, logging, and reconciliation are services, not LLM Agents.
- **Small Agent surface:** initial core roles are approximately ResearchAgent, StoryArchitectAgent, ChapterPlannerAgent, WriterAgent, CriticAgent, and RewriteAgent.
- **Canonical StoryState:** story truth lives in versioned StoryState, not independent Agent memories.
- **Artifact-first:** generated/reviewed assets are versioned, hashed, traceable to source inputs, prompt/model version, and runs.
- **Selective human gates:** human attention is reserved for high-value decisions and anomalies.
- **Provider-agnostic:** models/tools/storage sit behind explicit provider contracts.
- **Eval-driven complexity:** new Agent roles or extra model passes should justify their quality/cost impact through evals.

## Workflow shape

Use small composable workflows instead of one large 20+ step pipeline:

1. Research ingestion / hotspot workflow.
2. Opportunity intelligence and approval.
3. Book bootstrap and canonical StoryState initialization.
4. Chapter planning and `StoryContextSnapshot` creation.
5. `Writer → deterministic verify → Critic → Rewrite if needed → verify → finalize`.
6. Publishing and operations later.

## Feishu integration

Production runtime should target official Feishu/Lark SDK or official OpenAPI/Base v3 behind a storage provider boundary.

- Domain IDs such as `step_run_id` and `chapter_version_id` are never interchangeable with Feishu `record_id`.
- Ambiguous create outcomes use business-key reconciliation instead of blind POST retry.
- `lark-cli` and official MCP are intended for development, schema inspection, migration, operations, and agent-assisted administration rather than the backend's primary runtime path.

## Non-goals for v0.2

No Kubernetes, Kafka, Redis, Celery, Temporal, microservices, service mesh, distributed scheduler, Agent message bus, 20+ autonomous Agent topology, or second primary database unless real workload data demonstrates a need.

## Current roadmap

- **M1 — Foundation (v0.1 legacy):** completed baseline FastAPI, Feishu repository, execution primitives, Vercel shell.
- **M2 — Research ingestion and hotspot workflow.**
- **M2.5 — Harness v0.2 architecture alignment:** deterministic Harness Kernel, Feishu Base v3 feasibility/provider boundary, Artifact/ModelRouter/tracing/eval foundations.
- **M3 — Opportunity intelligence and approval flow.**
- **M4 — Canonical Story State and chapter loop.**

## Development

```bash
cd backend
python -m pip install -e ".[dev]"
python -m ruff check app tests
BACKEND_API_KEY=local-test-key python -m pytest tests -q -m "not integration" --cov=app
python -m build
```

Frontend (Node 24):

```bash
cd frontend
nvm use
npm ci
npm run check
```

CI requires workflow lint, Python lint, backend behavior tests with at least 87.82%
coverage, an installable backend package, frontend lint/type checks, and a production
build. Use **CI quality gate** as the required status check. See
[CI and deployment gates](docs/ci-cd.md) for reports, local commands, merge protection,
and deployment integration.

## Documents

- [Architecture](docs/architecture.md)
- [Feishu schema](docs/feishu-schema.md)
- [Agent design](docs/agent-team.md)
- [Pipeline v0.1 history](docs/pipeline-v0.1.md)
- [API surface](docs/api-surface.md)
- [Linear mapping](docs/linear-mapping.md)
- [CI and deployment gates](docs/ci-cd.md)

## Project tracking

Linear project: **NovelOps Agent Harness v0.2**

GitHub Issues mirror the implementation work tracked in Linear.
