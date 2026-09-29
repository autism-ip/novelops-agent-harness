# Feishu Bitable Schema

Feishu Bitable is the only database for v0.1.

It stores:

- Task state.
- Agent registry and state.
- Agent run history.
- Content artifacts.
- Human approvals.
- Revision tasks.
- Chapter versions.
- Agent Team snapshots.

## Core tables

## 1. Agents

Agent registry.

| Field | Purpose |
|---|---|
| `agent_id` | Unique Agent ID. |
| `agent_name` | Human-readable name. |
| `agent_role` | crawler / analysis / writer / reviewer / system. |
| `scope` | system / book. |
| `enabled` | Whether the Agent can run. |
| `model_provider` | LLM provider. |
| `model_name` | Model name. |
| `prompt_version` | Prompt version. |
| `input_schema` | Input schema reference or JSON. |
| `output_schema` | Output schema reference or JSON. |
| `tools_allowed` | Allowed tools. |
| `description` | Role description. |

## 2. AgentStates

Current Agent state and memory.

| Field | Purpose |
|---|---|
| `agent_state_id` | State ID. |
| `agent_id` | Linked Agent. |
| `book_id` | Linked book, empty for system Agents. |
| `status` | idle / running / waiting / stale / disabled. |
| `current_state` | Current knowledge and reasoning state. |
| `memory_summary` | Long-term memory summary. |
| `locked_rules` | Constraints the Agent must not violate. |
| `open_questions` | Questions awaiting human input. |
| `last_input_ref` | Last input artifact reference. |
| `last_output_ref` | Last output artifact reference. |
| `last_seen_chapter` | Latest chapter observed. |
| `risk_flags` | Known risks. |
| `updated_at` | Last update time. |

## 3. AgentRuns

Every Agent execution.

| Field | Purpose |
|---|---|
| `agent_run_id` | Run ID. |
| `agent_id` | Executed Agent. |
| `pipeline_run_id` | Parent PipelineRun. |
| `step_run_id` | Parent StepRun. |
| `book_id` | Linked book. |
| `input_refs` | Input artifact references. |
| `output_refs` | Output artifact references. |
| `model` | Model used. |
| `prompt_version` | Prompt version used. |
| `status` | success / failed. |
| `error_message` | Failure message. |
| `started_at` | Start time. |
| `finished_at` | End time. |

## 4. PipelineRuns

Pipeline-level state.

| Field | Purpose |
|---|---|
| `pipeline_run_id` | Pipeline run ID. |
| `pipeline_type` | Example: `douyin_to_novel`. |
| `status` | pending / running / waiting_approval / failed / completed / paused. |
| `current_step` | Current step key. |
| `source_hotspot_id` | Source hotspot. |
| `book_id` | Linked book if created. |
| `operator` | User who started it. |
| `created_at` | Created time. |
| `updated_at` | Updated time. |
| `error_message` | Pipeline-level error. |

## 5. StepRuns

Step-level state.

| Field | Purpose |
|---|---|
| `step_run_id` | Step run ID. |
| `pipeline_run_id` | Parent PipelineRun. |
| `step_key` | Step key. |
| `assigned_agent_id` | Agent responsible for this step. |
| `depends_on` | Dependency step keys. |
| `status` | pending / running / success / failed / blocked / skipped. |
| `input_refs` | Input artifact references. |
| `output_refs` | Output artifact references. |
| `lease_owner` | Worker instance that claimed it. |
| `lease_until` | Claim expiration time. |
| `retry_count` | Retry count. |
| `error_message` | Error details. |
| `started_at` | Start time. |
| `finished_at` | Finish time. |

## 6. Hotspots

Normalized Douyin hotspot records.

| Field | Purpose |
|---|---|
| `hotspot_id` | Hotspot ID. |
| `source` | `douyin`. |
| `rank` | Hotspot rank. |
| `title` | Hotspot title. |
| `url` | Source URL. |
| `heat_value` | Heat value. |
| `category` | Category. |
| `captured_at` | Capture time. |
| `raw_json` | Raw payload. |
| `dedupe_hash` | Deduplication key. |
| `status` | new / normalized / analyzed / approved / discarded. |

## 7. HotspotAnalyses

Hit-pattern and novelization analysis.

| Field | Purpose |
|---|---|
| `analysis_id` | Analysis ID. |
| `hotspot_id` | Source hotspot. |
| `summary` | Hotspot summary. |
| `core_emotions` | Core emotions. |
| `hit_patterns` | Hit patterns. |
| `novel_genres` | Novel genres. |
| `novelization_angles` | Novelization angles. |
| `reader_promise` | Reader promise. |
| `risk_level` | Risk level. |
| `risk_notes` | Risk notes. |
| `writability_score` | Writability score. |
| `approval_status` | pending / approved / rejected / revise. |

## 8. TitleCandidates

| Field | Purpose |
|---|---|
| `title_id` | Title ID. |
| `analysis_id` | Source analysis. |
| `title` | Novel title. |
| `hook` | One-line hook. |
| `selling_point` | Selling point. |
| `click_score` | Click score. |
| `genre_fit_score` | Genre fit. |
| `risk_notes` | Risk notes. |
| `approval_status` | pending / approved / rejected. |

## 9. CoverPlans

| Field | Purpose |
|---|---|
| `cover_id` | Cover plan ID. |
| `title_id` | Source title. |
| `visual_direction` | Main visual direction. |
| `main_elements` | Visual elements. |
| `style` | Style. |
| `cover_prompt` | Image prompt. |
| `negative_prompt` | Negative prompt. |
| `cover_asset_url` | Optional generated image URL. |
| `approval_status` | pending / approved / rejected. |

## 10. Books

| Field | Purpose |
|---|---|
| `book_id` | Book ID. |
| `hotspot_id` | Source hotspot. |
| `analysis_id` | Source analysis. |
| `title_id` | Approved title. |
| `cover_id` | Approved cover plan. |
| `book_title` | Book title. |
| `genre` | Genre. |
| `status` | planning / writing / reviewing / paused / ready. |
| `mini_bible` | MiniBible JSON/text. |
| `created_at` | Created time. |

## 11. ChapterBriefs

| Field | Purpose |
|---|---|
| `brief_id` | Brief ID. |
| `book_id` | Book ID. |
| `chapter_no` | Chapter number. |
| `chapter_title` | Chapter title. |
| `opening_hook` | Opening hook. |
| `scene_goal` | Scene goal. |
| `conflict` | Conflict. |
| `payoff` | Payoff. |
| `ending_hook` | Ending hook. |
| `approval_status` | pending / approved / rejected. |

## 12. ChapterVersions

| Field | Purpose |
|---|---|
| `version_id` | Version ID. |
| `book_id` | Book ID. |
| `chapter_no` | Chapter number. |
| `version_no` | v1 / v2 / v3. |
| `chapter_title` | Chapter title. |
| `content` | Chapter text. |
| `status` | New rows: candidate / review / final. Legacy statuses remain readable. |
| `agent_team_snapshot_id` | Legacy snapshot reference; new chapter loop writes do not use it. |
| `artifact_id` | Immutable ChapterVersion Artifact ID (additive v0.2 field). |
| `story_context_snapshot_id` | Immutable StoryContextSnapshot Artifact ID used by the version (additive). |
| `source_refs_json` | Exact source Artifact IDs as canonical JSON (additive). |
| `content_hash` | ChapterVersion Artifact SHA-256 (additive). |
| `verifier_artifact_id` | Successful deterministic verifier Artifact ID (additive). |
| `run_id` | Harness chapter run ID (additive). |
| `locked_at` | Final lock timestamp, set only on the selected version (additive). |
| `locked_by` | Final lock operator, set only on the selected version (additive). |
| `review_report_id` | CriticReport Artifact ID on the selected review version. |
| `prompt_version` | Prompt version. |
| `created_at` | Created time. |

## 13. ReviewReports

| Field | Purpose |
|---|---|
| `review_id` | Review ID. |
| `target_type` | title / cover / chapter / mini_bible. |
| `target_id` | Target artifact ID. |
| `reviewer_agent` | Reviewer Agent. |
| `scores` | Scores JSON. |
| `problems` | Problems JSON. |
| `suggestions` | Suggestions. |
| `overall_status` | pass / revise / reject. |
| `created_at` | Created time. |

## 14. RevisionTasks

ZEN-41 stores a durable chapter revision command here before enqueueing its rewrite run. The existing constraint columns carry JSON arrays. Add the new fields below to the Feishu table before enabling the review desk; domain IDs are used for actions, not Feishu record IDs.

| Field | Purpose |
|---|---|
| `revision_task_id` | Revision task ID. |
| `target_type` | `chapter_version` for chapter editorial revision. |
| `target_id` | Book/chapter logical target. |
| `from_version_id` | Source version. |
| `source_artifact_id` | Exact source ChapterVersion Artifact (ZEN-41). |
| `book_id` | Source Book ID (ZEN-41). |
| `chapter_no` | Chapter number (ZEN-41). |
| `revision_type` | `human` for editor-directed revision. |
| `reason` | Reason. |
| `must_keep` | Required preserved elements. |
| `must_change` | Required changes. |
| `do_not_change` | Forbidden changes. |
| `assigned_agent_id` | Agent assigned. |
| `created_by` | Editor identity (ZEN-41). |
| `run_id` | Deterministic rewrite run ID (ZEN-41). |
| `request_json` | Exact frozen generation request for safe retry (ZEN-41). |
| `status` | `open` until enqueue, then `queued`. |
| `created_at` | Created time. |

## 15. AgentTeamSnapshots

| Field | Purpose |
|---|---|
| `snapshot_id` | Snapshot ID. |
| `book_id` | Book ID. |
| `chapter_no` | Chapter number. |
| `agent_states_json` | Frozen Agent Team state. |
| `used_by_version_id` | ChapterVersion using it. |
| `created_at` | Created time. |

## 16. ApprovalEvents

| Field | Purpose |
|---|---|
| `approval_id` | Approval event ID. |
| `target_type` | Artifact type. |
| `target_id` | Artifact ID. |
| `action` | approve / reject / revise / regenerate / lock_final. |
| `operator` | Human operator. |
| `comment` | Human comment. |
| `created_at` | Created time. |

## v0.2 additive Book / StoryState migration (ZEN-38)

Provision `StoryStates` as a new Feishu Base table and set `FEISHU_TABLE_ID_STORY_STATES`. Its business key is `story_state_id`; the primary field must remain writable text. Required fields are `story_state_id`, `book_id`, `version` (number), `artifact_id`, `content_hash`, `source_refs_json`, and `created_at`. Store JSON references as text, matching the existing Artifact projection conventions.

Add writable fields to the existing `Books` table: `bootstrap_hash`, `source_refs_json`, `story_state_id`, `story_state_version` (number), and `story_state_hash`. Existing Book fields remain. The runtime sets `BOOKS_ENABLED=true` only after these fields and the new table exist. `CREATIVE_ENABLED`, `RESEARCH_ENABLED`, generation, and the Harness must also be configured.

The `Book` record is created with `status=initializing`, then an immutable StoryState Artifact and one `StoryStates` version row are persisted. The final `ready` update points to their hash. A retry with the same approved source refs and stable business IDs reconciles an interrupted initialization. Never auto-create a second record after an ambiguous Feishu POST; inspect the journal and Base by business ID if a create remains uncertain.

Legacy `mini_bible`, `AgentStates`, and `AgentTeamSnapshots` remain readable but are not written by book bootstrap and are not sources of canonical book truth. Do not drop their fields or tables as part of this additive migration. Future chapter work reads the canonical state through `StoryContextProvider` and may replace legacy snapshots with versioned `StoryContextSnapshot` artifacts in its own migration.
