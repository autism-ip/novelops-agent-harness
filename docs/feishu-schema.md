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
| `status` | draft / reviewed / revision_required / final. |
| `agent_team_snapshot_id` | Snapshot used. |
| `review_report_id` | Review report. |
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

| Field | Purpose |
|---|---|
| `revision_task_id` | Revision task ID. |
| `target_type` | chapter / title / cover / mini_bible. |
| `target_id` | Target artifact. |
| `from_version_id` | Source version. |
| `revision_type` | minor_revise / rewrite / regenerate. |
| `reason` | Reason. |
| `must_keep` | Required preserved elements. |
| `must_change` | Required changes. |
| `do_not_change` | Forbidden changes. |
| `assigned_agent_id` | Agent assigned. |
| `status` | pending / running / completed / cancelled. |
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
