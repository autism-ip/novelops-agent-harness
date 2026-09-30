# Architecture v0.2

## System positioning

NovelOps is a Feishu-first, local-first modular Harness for AI-assisted web-novel production. It is optimized for a single operator and high cost-efficiency first, while preserving clean extension points for long-term automation and future multi-user deployment.

The system deliberately separates deterministic execution from non-deterministic intelligence.

- **Harness services** own workflow execution, state transitions, retries, reconciliation, validation, approvals, tracing, and cost controls.
- **Agents** are reserved for semantic reasoning and generation.

## High-level architecture

```text
Next.js / Vercel
  ↓ HTTP / SSE
FastAPI modular monolith
  ↓
Harness Kernel
  ├─ Workflow Engine
  ├─ State Machine
  ├─ Single Scheduler / Single Writer
  ├─ Context Builder
  ├─ Agent Runtime
  ├─ Validator / Verifier
  ├─ Retry / Recovery / Reconciliation
  ├─ Approval
  └─ Trace / Usage / Cost
  ↓
Provider layer
  ├─ ModelProvider: DeepSeek / OpenAI / future
  ├─ ToolProvider: OpenCLI / web / APIs / image tools
  └─ StorageProvider: Feishu Base / Docs / Drive
```

## Product layer

### Frontend

- Next.js deployed on Vercel.
- Talks only to backend APIs.
- Book/workflow-centric UX rather than Agent-centric UX.
- Primary surfaces: Dashboard, Ideas/Hotspots, Books, Writing, Review, Publish, System/Trace.
- Model/Agent implementation details live in developer/system views, not primary writing flows.

### Backend

- Local persistent FastAPI service.
- Modular monolith for v0.2.
- One authoritative scheduler and one machine writer.
- Owns orchestration, provider calls, validation, reconciliation, approvals, StoryState commits, and trace/cost accounting.

## Harness Kernel

### Workflow Engine

Executes small composable subworkflows rather than a single long pipeline.

Core workflow families:

1. Research ingestion / hotspot.
2. Opportunity intelligence / title / cover.
3. Book bootstrap.
4. Chapter planning.
5. Chapter generation / review / revision.
6. Publishing later.

### State Machine

WorkflowRun and StepRun state changes go through explicit transition code. New business code must not directly mutate lifecycle states.

Typical StepRun states:

```text
pending → ready → running
                  ├─ success
                  ├─ retry_wait
                  ├─ waiting_human
                  ├─ failed
                  └─ cancelled
```

### Single Scheduler / Single Writer

v0.2 targets one user and one authoritative backend process.

- One scheduler decides what is runnable.
- One machine writer serializes Feishu runtime mutations.
- Distributed worker election/lease contention is not a v0.2 requirement.
- Existing v0.1 lease primitives may remain temporarily for compatibility but should not shape new design.

### Idempotency and reconciliation

Feishu Base is not treated as an exactly-once transactional queue.

- Every create path has a stable business key where practical.
- Ambiguous create outcomes are reconciled by business key before another create attempt.
- Blind retry of uncertain POST creates is avoided.
- Domain IDs and Feishu `record_id` are strictly separated.

## Storage architecture

### Feishu-first

Feishu Base remains the primary structured SSOT for v0.2 because the current workload is low-concurrency, single-operator, and benefits strongly from human visibility/editability.

Use Feishu ecosystem capabilities intentionally:

- **Base:** structured business/runtime state.
- **Docs:** long-form human-readable content where useful.
- **Drive:** assets/reference files.
- **Workflow:** notifications, human workflow, and HTTP callbacks where appropriate.
- **lark-cli / official MCP:** development, schema inspection, migration, operations, and agent-assisted administration.

Production backend integration should target official SDK/OpenAPI/Base v3 behind a `StorageProvider`/repository boundary.

Do not add SQLite/PostgreSQL as a second primary store until production-like tests demonstrate a concrete need such as multi-user concurrency, SQL-heavy querying, transactional requirements, or Feishu API limits.

## Domain model

### Canonical StoryState

Story truth belongs to a single versioned canonical state, not to independent long-lived Agent memories.

Core namespaces:

```text
StoryState
├─ StoryBible
├─ World
├─ Characters
├─ PowerSystem
├─ Timeline
├─ Plot
├─ Foreshadowing
└─ StyleContract
```

Agents read StoryState and propose structured changes. Harness validation/consistency checks decide what may be committed.

### Artifact

Important generated/reviewed outputs are first-class versioned Artifacts.

Examples:

- HotspotAnalysis
- OpportunityAnalysis
- TitleCandidate
- CoverPlan
- StoryBible
- ChapterBrief
- StoryContextSnapshot
- ChapterVersion
- CriticReport
- RevisionInstruction

Artifact metadata should capture at least type, version, source refs, content hash, creator/run refs, and timestamps.

### StoryContextSnapshot

Before chapter generation, Context Builder freezes explicit StoryState/Artifact versions needed for the chapter. ChapterVersion references the snapshot used to generate it.

This replaces the old AgentTeamSnapshot concept and provides reproducibility without copying independent Agent memories.

## Agent Runtime

Only non-deterministic semantic work is represented as an Agent.

Initial core roles are approximately:

- `ResearchAgent`
- `StoryArchitectAgent`
- `ChapterPlannerAgent`
- `WriterAgent`
- `CriticAgent`
- `RewriteAgent`

The following are Harness services, not Agents:

- orchestration
- task management
- schema validation
- deterministic verification
- logging/tracing
- approvals
- state synchronization/reconciliation

Agent count should grow only when evals show a measurable quality/cost benefit.

## Chapter loop

```text
Build Context
    ↓
Chapter Planner
    ↓
Writer
    ↓
Deterministic Verifier
    ↓
Critic
    ↓
revision required?
 ┌──┴──┐
 yes   no
  ↓     │
Rewrite │
  ↓     │
Verify ◄┘
  ↓
Selective Human Gate
  ↓
Final
```

Avoid unconditional chains of full-text rewriting such as `Writer → StyleAgent → AntiAIFlavorAgent → ReviewAgent`.

## Verification

### Deterministic verification

Use code for checks code can reliably perform, including schema validity, IDs/references, lifecycle constraints, chapter metadata, explicit forbidden rules, hard timeline/power-system constraints where modeled, and version integrity.

### Semantic critique

Use LLMs for pacing, emotional payoff, voice/style, dialogue quality, reader promise, continuity requiring interpretation, repetition, and AI-like phrasing.

## Model architecture

Use `ModelRouter` plus provider adapters.

Business/workflow code requests a logical route/capability rather than hard-coding a provider model. DeepSeek can serve as the default cost-efficient route, while OpenAI and future providers remain available for premium/eval/fallback roles.

Every model call should record provider/model, prompt version/hash, input/output refs, token usage, latency, retries, estimated cost, and failure class.

## Human-in-the-loop

Human attention is treated as scarce.

Default automation should stop only at high-value decisions or anomalies, such as:

- opportunity/book selection
- initial StoryBible approval
- major story-direction changes
- severe review/consistency problems
- final publication

Routine normalization, context building, verification, retries, and low-risk processing should not require manual confirmation.

## Reliability rules

- Stable business idempotency keys for create operations where practical.
- No silent overwrite of chapter/artifact history.
- Schema validation before persistence of model outputs.
- Explicit transition functions for run lifecycle state.
- Reconciliation after ambiguous persistence outcomes.
- Structured failure classes and bounded retry policies.
- Trace model/tool usage and cost.
- Frontend never receives Feishu/LLM/OpenCLI secrets.

## Non-goals for v0.2

- Kubernetes.
- Kafka.
- Redis/Celery.
- Temporal.
- Microservices/service mesh.
- Distributed scheduler/worker pool.
- Agent-to-Agent message bus.
- 20+ autonomous Agent topology.
- Full Event Sourcing.
- Second primary database without demonstrated need.

## Evolution path

### Personal MVP / long-term personal use

FastAPI modular monolith + Single Writer + Feishu-first + provider-based models/tools.

### Multi-user growth

When justified by measured workload:

- Feishu runtime state can move behind the same provider contract to PostgreSQL.
- Single Writer can evolve into a worker pool.
- large artifacts can move to object storage.
- durable workflow infrastructure can be evaluated only when execution complexity warrants it.

The domain/workflow model should remain stable across those infrastructure changes.
# v0.2 implementation note

The deterministic runtime is documented in [Harness v0.2](harness-v02.md).
That document supersedes the legacy system-Agent/lease execution descriptions
below for new code. Semantic Agents remain model-backed handlers; scheduling,
transitions, approvals and recovery belong to the kernel. Feishu remains SSOT.
