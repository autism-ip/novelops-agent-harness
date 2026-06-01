# NovelOps Agent Team Harness

NovelOps is a front/back separated Agent Team Harness for AI-assisted web-novel production.

## v0.1 Goal

Build a controllable MVP that turns Douyin public hotspots into reviewed web-novel drafts.

The first pipeline is:

```text
Douyin public hotspots
  ↓
Hotspot normalization
  ↓
Hit-pattern and novelization analysis
  ↓
Human approval
  ↓
Title and cover-plan generation
  ↓
Book creation and Agent Team initialization
  ↓
MiniBible generation
  ↓
Chapter brief generation
  ↓
Chapter draft generation
  ↓
AI review
  ↓
Human review
  ↓
Revision or final lock
```

## Architecture

```text
Vercel Frontend
  ↓ HTTP API
Local Persistent Backend / Agent Team Harness
  ↓
Feishu Bitable as the only database
  ↓
External tools: OpenCLI, LLM APIs, optional image APIs
```

## Core constraints

- Frontend is deployed on Vercel and only handles visualization, operation, review, and approvals.
- Backend is a local persistent FastAPI service and owns execution.
- Feishu Bitable is the only database in v0.1.
- OpenCLI is used for Douyin public hotspot extraction.
- Every functional role is represented as an Agent.
- Every Agent has state, memory, input schema, output schema, and run records.
- Every important artifact is written to Feishu.
- Key steps require human approval.
- Revisions are versioned; no overwrite.

## Backend gates

```bash
cd backend
python -m pip install -e ".[dev]"
BACKEND_API_KEY=local-test-key python -m pytest tests -q
```

The CI gate is behavior-based: it checks endpoint response contracts, API key enforcement, sanitized config output, missing env failure, and ZEN-28 layout. A backend that merely starts is not sufficient. If implementation is absent or incomplete, this gate should fail.

## Documents

- [Architecture](docs/architecture.md)
- [Feishu schema](docs/feishu-schema.md)
- [Agent Team design](docs/agent-team.md)
- [v0.1 pipeline](docs/pipeline-v0.1.md)
- [API surface](docs/api-surface.md)
- [Linear mapping](docs/linear-mapping.md)

## Linear project

Linear project: [NovelOps Agent Team Harness v0.1](https://linear.app/zenhungyep/project/novelops-agent-team-harness-v01-7a6c4cb8b870)

Architecture document: [Architecture and technical plan](https://linear.app/zenhungyep/document/architecture-and-technical-plan-34f4ffbdab82)
