# ZEN-29: Implement Feishu Bitable Repository Layer

> **For Claude:** REQUIRED SUB-SKILL: Load `superpowers:executing-plans` skill using the Skill tool to implement this plan task-by-task.

**Goal:** Implement Feishu Bitable as the sole database for v0.1 — client wrapper, table map config, and repository interfaces for all 16 core tables.

**Architecture:** Repository pattern over Feishu Bitable REST API. A thin HTTP client handles auth and transport. A table map config centralizes all table/field IDs. A generic BaseRepository provides CRUD. Concrete repositories per table expose domain-specific queries.

**Tech Stack:** Python 3.12+, FastAPI, lark-oapi (Feishu SDK), pydantic, pytest, pytest-asyncio

**Design Support:**
- [ZEN-29 Linear Issue](https://linear.app/zenhungyep/issue/ZEN-29/implement-feishu-bitable-repository-layer-and-core-schema-mapping)
- [Feishu Schema](../../docs/feishu-schema.md)
- [ZEN-28 (prerequisite)](../2026-05-31-zen28-fastapi-plan/_index.md)

## Context

NovelOps uses Feishu Bitable as its only database for v0.1. The schema defines 16 tables covering agents, pipeline runs, hotspots, books, chapters, reviews, and approvals. ZEN-28 established the FastAPI skeleton. ZEN-29 builds the data access layer that all subsequent agent and pipeline code depends on.

**Why Feishu Bitable:** Zero infra overhead, built-in UI for human review, accessible to non-technical operators, API-first design.

**Current state (ZEN-28):** FastAPI app with health/status endpoints, Pydantic settings (FEISHU_APP_ID, FEISHU_APP_SECRET configured), API key guard middleware.

**Target state (ZEN-29):** Full repository layer — `feishu/client.py` handles auth, `feishu/table_map.py` maps all 16 tables, `feishu/repositories/` provides CRUD per table.

## Execution Plan

```yaml
tasks:
  - id: "001"
    subject: "Add lark-oapi dependency"
    slug: "add-lark-oapi-dependency"
    type: "setup"
    depends-on: []
  - id: "002"
    subject: "Create Feishu client wrapper"
    slug: "create-feishu-client"
    type: "impl"
    depends-on: ["001"]
  - id: "003"
    subject: "Create table map config"
    slug: "create-table-map-config"
    type: "impl"
    depends-on: ["001"]
  - id: "004"
    subject: "Create base repository with generic CRUD"
    slug: "create-base-repository"
    type: "impl"
    depends-on: ["002"]
  - id: "005"
    subject: "Create concrete repositories for all 16 tables"
    slug: "create-concrete-repositories"
    type: "impl"
    depends-on: ["002", "003", "004"]
  - id: "006"
    subject: "Write unit tests for client and repositories"
    slug: "write-unit-tests"
    type: "test"
    depends-on: ["005"]
  - id: "007"
    subject: "Verify integration with Feishu API"
    slug: "verify-feishu-integration"
    type: "test"
    depends-on: ["006"]
```

**Task File References (for detailed BDD scenarios):**
- [Task 001: Add lark-oapi dependency](./task-001-add-lark-oapi-dependency.md)
- [Task 002: Create Feishu client wrapper](./task-002-create-feishu-client.md)
- [Task 003: Create table map config](./task-003-create-table-map-config.md)
- [Task 004: Create base repository](./task-004-create-base-repository.md)
- [Task 005: Create concrete repositories](./task-005-create-concrete-repositories.md)
- [Task 006: Write unit tests](./task-006-write-unit-tests.md)
- [Task 007: Verify Feishu integration](./task-007-verify-feishu-integration.md)

## BDD Coverage

| Acceptance Criterion | Task |
|---------------------|------|
| Backend can create/read/update records in Feishu | 002, 004, 005, 006, 007 |
| Table names and field mappings are centralized | 003, 006 |
| Repository layer hides Feishu API details | 004, 005, 006 |

## Dependency Chain

```
task-001 (setup: lark-oapi dep)
    ├─→ task-002 (feishu client)
    │       ├─→ task-004 (base repository)
    │       │       └─→ task-005 (concrete repos) ─→ task-006 (tests) ─→ task-007 (integration)
    │       └─→ task-005 (concrete repos)
    └─→ task-003 (table map config)
            └─→ task-005 (concrete repos)
```

**Analysis:**
- No circular dependencies
- task-002 and task-003 can proceed in parallel after task-001
- task-004 depends only on task-002 (client)
- task-005 synthesizes client + table map + base repo
- Clean dependency → implementation → test → integration flow
