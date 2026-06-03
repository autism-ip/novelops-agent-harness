# NovelOps Agent Harness — AI-assisted web-novel production system

Tech stack: FastAPI + pytest + GitHub Actions + Next.js + Feishu Bitable + OpenCLI + LLM APIs

<directory>
docs/ - Design documents and planning (6 files)
  plans/ - Implementation plans and strategies
.github/ - CI workflow definitions (backend behavior gates)
backend/ - Local persistent FastAPI backend skeleton and behavior tests
frontend/ - Next.js 16 + shadcn/ui + Tailwind CSS 4 Vercel frontend
</directory>

<config>
.gitignore - Python cache, local env, pytest cache, and egg-info ignore rules
README.md - Project overview, architecture summary, document index
backend/pyproject.toml - Backend package metadata, dependencies, pytest configuration
backend/.env.example - Backend environment variable template with placeholders only
.github/workflows/backend-gates.yml - CI gate that runs backend behavior contract tests
docs/architecture.md - System architecture, module layout, stability rules
docs/agent-team.md - Agent roles, state model, per-book team design
docs/feishu-schema.md - 16 Feishu Bitable tables schema
docs/pipeline-v0.1.md - 22-step pipeline, status rules, reliability rules
docs/api-surface.md - REST API endpoints for frontend-backend communication
docs/linear-mapping.md - Linear project, milestones, and issue mapping
</config>

## Linear Project

14 issues across 4 milestones (all Todo):

| Milestone | Issues |
|-----------|--------|
| M1 Foundation | ZEN-28, ZEN-29, ZEN-30, ZEN-31 |
| M2 Douyin Hotspot | ZEN-32, ZEN-33, ZEN-34 |
| M3 Analysis | ZEN-35, ZEN-36, ZEN-37 |
| M4 Book & Chapters | ZEN-38, ZEN-39, ZEN-40, ZEN-41 |

## Branch Strategy

One feature branch per issue: `feature/ZEN-{n}-{short-slug}`

Development order: ZEN-28 → ZEN-29 → ZEN-30 → (ZEN-31 ∥ ZEN-32) → ZEN-33 → ZEN-34 → ZEN-35 → ZEN-36 → (ZEN-37 ∥ ZEN-38) → ZEN-39 → ZEN-40 → ZEN-41

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
