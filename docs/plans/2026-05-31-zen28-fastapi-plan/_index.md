# ZEN-28: Initialize Backend FastAPI Harness Skeleton

> **For Claude:** REQUIRED SUB-SKILL: Load `superpowers:executing-plans` skill using the Skill tool to implement this plan task-by-task.

**Goal:** Create the local persistent backend skeleton for the NovelOps Harness with health/status endpoints, environment config, and API key guard.

**Architecture:** FastAPI application with modular route structure, Pydantic settings for environment config, and middleware-based API key authentication. All secrets stay backend-only.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, Pydantic Settings, pytest, httpx (test client)

**Design Support:**
- [ZEN-28 Linear Issue](https://linear.app/zenhungyep/issue/ZEN-28/initialize-backend-fastapi-harness-skeleton)
- [Architecture](../../docs/architecture.md)
- [API Surface](../../docs/api-surface.md)

## Context

NovelOps Agent Harness is a greenfield project with zero code. The backend needs a solid foundation before any agent or pipeline logic can be built. ZEN-28 establishes the FastAPI skeleton that all subsequent issues (ZEN-29 through ZEN-41) will build upon.

This is the dependency chain root — every other issue depends on this being merged first.

## Execution Plan

```yaml
tasks:
  - id: "001"
    subject: "Create project structure and dependencies"
    slug: "create-project-structure"
    type: "setup"
    depends-on: []
  - id: "002"
    subject: "Create environment config with Pydantic Settings"
    slug: "create-env-config"
    type: "impl"
    depends-on: ["001"]
  - id: "003"
    subject: "Create health and status endpoints"
    slug: "create-health-status-endpoints"
    type: "impl"
    depends-on: ["001"]
  - id: "004"
    subject: "Create API key guard middleware"
    slug: "create-api-key-guard"
    type: "impl"
    depends-on: ["001"]
  - id: "005"
    subject: "Create integration tests for all endpoints"
    slug: "create-integration-tests"
    type: "test"
    depends-on: ["002", "003", "004"]
  - id: "006"
    subject: "Verify full backend startup and acceptance criteria"
    slug: "verify-acceptance-criteria"
    type: "test"
    depends-on: ["005"]
```

**Task File References (for detailed BDD scenarios):**
- [Task 001: Create project structure](./task-001-create-project-structure.md)
- [Task 002: Create environment config](./task-002-create-env-config.md)
- [Task 003: Create health and status endpoints](./task-003-create-health-status-endpoints.md)
- [Task 004: Create API key guard middleware](./task-004-create-api-key-guard.md)
- [Task 005: Create integration tests](./task-005-create-integration-tests.md)
- [Task 006: Verify acceptance criteria](./task-006-verify-acceptance-criteria.md)

## BDD Coverage

All acceptance criteria from ZEN-28 are covered:

| Acceptance Criterion | Task |
|---------------------|------|
| `GET /api/system/health` returns backend status | 003, 005, 006 |
| `GET /api/system/status` returns worker/Feishu/OpenCLI placeholders | 003, 005, 006 |
| Project can run locally with `uvicorn app.main:app` | 001, 006 |
| Secrets remain backend-only | 002, 004, 005 |

## Dependency Chain

```
task-001 (setup)
    ├─→ task-002 (env config)
    │       └─→ task-005 (integration tests)
    ├─→ task-003 (endpoints)
    │       └─→ task-005 (integration tests)
    └─→ task-004 (api key guard)
            └─→ task-005 (integration tests)
                    └─→ task-006 (acceptance verification)
```

**Analysis**:
- No circular dependencies
- task-002, 003, 004 can proceed in parallel after task-001
- task-005 integrates all three before task-006 final verification
- Clean foundation → features → integration → acceptance flow
