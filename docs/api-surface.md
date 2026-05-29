# API Surface

The frontend talks only to the backend API. It never calls Feishu, OpenCLI, or LLM providers directly.

## System

```http
GET /api/system/health
GET /api/system/status
GET /api/system/config
```

### Example system status

```json
{
  "backend_status": "running",
  "worker_status": "running",
  "feishu_status": "ok",
  "opencli_status": "ok",
  "active_pipeline_runs": 3,
  "pending_steps": 12,
  "failed_steps": 1
}
```

## Pipelines

```http
POST /api/pipelines
GET /api/pipelines
GET /api/pipelines/{pipeline_run_id}
POST /api/pipelines/{pipeline_run_id}/pause
POST /api/pipelines/{pipeline_run_id}/resume
POST /api/pipelines/{pipeline_run_id}/retry
POST /api/pipelines/{pipeline_run_id}/advance
```

## Steps

```http
GET /api/steps
GET /api/steps/{step_run_id}
POST /api/steps/{step_run_id}/retry
POST /api/steps/{step_run_id}/skip
POST /api/steps/{step_run_id}/rerun
```

## Agents

```http
GET /api/agents
GET /api/agents/{agent_id}
GET /api/agents/states
GET /api/agents/runs
GET /api/books/{book_id}/agent-team
POST /api/agents/{agent_id}/run
POST /api/agents/{agent_id}/enable
POST /api/agents/{agent_id}/disable
```

## Hotspots

```http
POST /api/hotspots/fetch-douyin
GET /api/hotspots
GET /api/hotspots/{hotspot_id}
POST /api/hotspots/{hotspot_id}/analyze
POST /api/hotspots/{hotspot_id}/discard
```

## Analyses

```http
GET /api/analyses
GET /api/analyses/{analysis_id}
POST /api/analyses/{analysis_id}/approve
POST /api/analyses/{analysis_id}/reject
POST /api/analyses/{analysis_id}/revise
```

## Titles and cover plans

```http
GET /api/titles
GET /api/titles/{title_id}
POST /api/titles/{title_id}/approve
POST /api/titles/{title_id}/reject
POST /api/titles/{title_id}/revise

GET /api/covers
GET /api/covers/{cover_id}
POST /api/covers/{cover_id}/approve
POST /api/covers/{cover_id}/reject
POST /api/covers/{cover_id}/revise
```

## Books

```http
POST /api/books
GET /api/books
GET /api/books/{book_id}
GET /api/books/{book_id}/chapters
POST /api/books/{book_id}/init-agent-team
POST /api/books/{book_id}/generate-mini-bible
POST /api/books/{book_id}/generate-briefs
POST /api/books/{book_id}/generate-chapter
```

## Reviews

```http
GET /api/reviews
GET /api/reviews/{review_id}
POST /api/reviews/{review_id}/approve
POST /api/reviews/{review_id}/revise
POST /api/reviews/{review_id}/reject
POST /api/reviews/{review_id}/lock-final
```

## Revisions

```http
POST /api/revisions
GET /api/revisions
GET /api/revisions/{revision_task_id}
POST /api/revisions/{revision_task_id}/run
POST /api/revisions/{revision_task_id}/cancel
```

## Security

v0.1 can use a simple backend API token.

Frontend requests include:

```http
x-api-key: <token>
```

The backend stores:

- Feishu credentials.
- LLM API keys.
- OpenCLI environment.
- Image generation credentials, if any.

These secrets must not be exposed to the frontend.
