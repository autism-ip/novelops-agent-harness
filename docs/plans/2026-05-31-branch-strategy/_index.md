# Branch Strategy — Linear Issue Feature Branches

## Context

NovelOps Agent Harness v0.1 has 14 Linear issues across 4 milestones, all in Todo status.
The project is currently documentation-only (zero code). Each issue needs a dedicated feature branch
for isolated development with clean PR boundaries.

## Requirements

- One feature branch per Linear issue (14 total)
- Branches created from `main`
- Naming convention: `feature/ZEN-{n}-{short-slug}`
- Development follows dependency chain within each milestone
- Each branch maps 1:1 to a Linear issue for traceability

## Branch Map

### M1 — Foundation and Feishu schema

| Branch | Issue | Depends On |
|--------|-------|------------|
| `feature/ZEN-28-fastapi-skeleton` | ZEN-28 | — |
| `feature/ZEN-29-feishu-repo-layer` | ZEN-29 | ZEN-28 |
| `feature/ZEN-30-pipeline-worker-loop` | ZEN-30 | ZEN-28, ZEN-29 |
| `feature/ZEN-31-frontend-shell` | ZEN-31 | ZEN-28 |

### M2 — Douyin hotspot pipeline

| Branch | Issue | Depends On |
|--------|-------|------------|
| `feature/ZEN-32-opencli-adapter` | ZEN-32 | ZEN-28, ZEN-29 |
| `feature/ZEN-33-hotspot-agents` | ZEN-33 | ZEN-32 |
| `feature/ZEN-34-hotspots-ui` | ZEN-34 | ZEN-31, ZEN-33 |

### M3 — Analysis, title, and cover agents

| Branch | Issue | Depends On |
|--------|-------|------------|
| `feature/ZEN-35-analysis-agents` | ZEN-35 | ZEN-29, ZEN-30 |
| `feature/ZEN-36-title-cover-agents` | ZEN-36 | ZEN-35 |
| `feature/ZEN-37-approval-ui` | ZEN-37 | ZEN-31, ZEN-36 |

### M4 — Book Agent Team and chapter workflow

| Branch | Issue | Depends On |
|--------|-------|------------|
| `feature/ZEN-38-book-creation` | ZEN-38 | ZEN-36, ZEN-30 |
| `feature/ZEN-39-minibible-briefs` | ZEN-39 | ZEN-38 |
| `feature/ZEN-40-chapter-agents` | ZEN-40 | ZEN-39 |
| `feature/ZEN-41-review-desk-ui` | ZEN-41 | ZEN-31, ZEN-40 |

## Recommended Development Order

```text
Phase 1 (sequential):  ZEN-28 → ZEN-29 → ZEN-30
Phase 2 (parallel):    ZEN-31 ∥ ZEN-32
Phase 3 (sequential):  ZEN-33 → ZEN-34
Phase 4 (parallel):    ZEN-35 (can start after ZEN-30)
Phase 5 (sequential):  ZEN-36 → ZEN-37
Phase 6 (parallel):    ZEN-38 (can start after ZEN-36)
Phase 7 (sequential):  ZEN-39 → ZEN-40 → ZEN-41
```

## Design Documents

- [_index.md](./_index.md) — This file: context, requirements, branch map
- [bdd-specs.md](./bdd-specs.md) — Branch creation acceptance criteria
- [decisions.md](./decisions.md) — Naming convention and workflow decisions
