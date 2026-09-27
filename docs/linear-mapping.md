# Linear Mapping — v0.2

Linear project: **NovelOps Agent Harness v0.2**

Architecture document: **NovelOps Agent Harness v0.2 — Architecture and Technical Plan**

## Milestones

1. M1 — Foundation (v0.1 legacy)
2. M2 — Research ingestion and hotspot workflow
3. M2.5 — Harness v0.2 architecture alignment
4. M3 — Opportunity intelligence and approval flow
5. M4 — Canonical Story State and chapter loop

## Issues

| Linear | GitHub | Title | Milestone |
|---|---:|---|---|
| ZEN-28 | #1 | Initialize backend FastAPI harness skeleton | M1 |
| ZEN-29 | #2 | Implement Feishu Bitable repository layer and core schema mapping | M1 |
| ZEN-30 | #3 | Build PipelineRun, StepRun, and worker loop primitives | M1 |
| ZEN-31 | #4 | Create Vercel frontend shell and backend API client | M1 |
| ZEN-32 | #5 | Implement OpenCLI Douyin hotspot adapter integration | M2 |
| ZEN-33 | #6 | Implement hotspot ingestion and normalization workflow | M2 |
| ZEN-34 | #7 | Build Hotspots product page and manual controls | M2 |
| ZEN-104 | #20 | Refactor execution core to deterministic Harness Kernel and Single Writer | M2.5 |
| ZEN-105 | #21 | Validate Feishu Base v3 and refactor Feishu provider boundary | M2.5 |
| ZEN-106 | #22 | Add Artifact, ModelRouter, tracing, cost, and eval foundations | M2.5 |
| ZEN-35 | #8 | Implement research, novelization, and risk analysis workflow | M3 |
| ZEN-36 | #9 | Implement title and cover planning workflow | M3 |
| ZEN-37 | #10 | Build opportunity, title, and cover approval UI | M3 |
| ZEN-38 | #11 | Implement book bootstrap and canonical StoryState initialization | M4 |
| ZEN-39 | #12 | Implement StoryBible and chapter planning workflow | M4 |
| ZEN-40 | #13 | Implement chapter generation, critique, rewrite, and verification loop | M4 |
| ZEN-41 | #14 | Build chapter review desk with selective approval and final-lock actions | M4 |

## Architecture transition notes

- ZEN-28 through ZEN-32 are retained as historical implementation work.
- ZEN-104 through ZEN-106 form the v0.2 architecture-alignment gate before expanding the semantic Agent surface.
- Future work should follow the deterministic Harness + Feishu-first + canonical StoryState design in `docs/architecture.md`.
- GitHub Issues mirror Linear implementation scope; Linear remains the product/project planning source.

## Repository

GitHub repository: `autism-ip/novelops-agent-harness`
