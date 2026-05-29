# Agent Team Design

NovelOps treats the Harness itself as an Agent Team.

Each function is represented by an Agent with:

- A role.
- An input schema.
- An output schema.
- A prompt version.
- A tool permission set.
- State and memory persisted in Feishu.
- AgentRun records for every execution.

## System agents

| Agent | Responsibility |
|---|---|
| `OrchestratorAgent` | Decide which step is runnable and assign work. |
| `TaskManagerAgent` | Create, split, retry, pause, and resume tasks. |
| `SchemaGuardAgent` | Validate Agent outputs before persistence. |
| `LoggerAgent` | Record AgentRun, StepRun, errors, and timing. |
| `ApprovalAgent` | Handle approval gates, rejections, revision requests, and final locks. |
| `StateSyncAgent` | Keep Feishu state consistent after each step. |

## Data and analysis agents

| Agent | Responsibility |
|---|---|
| `DouyinHotspotCrawlerAgent` | Call OpenCLI to extract Douyin public hotspots. |
| `HotspotNormalizeAgent` | Normalize, deduplicate, and score raw hotspot records. |
| `HitPatternAnalysisAgent` | Extract hit-pattern structures and reader-emotion hooks. |
| `NovelizationAnalysisAgent` | Convert hotspots into web-novel directions. |
| `RiskScreenAgent` | Screen for sensitive, defamatory, low-quality, or infringement risk. |

## Creation agents

| Agent | Responsibility |
|---|---|
| `TitleAgent` | Generate novel title candidates, hooks, selling points, and scores. |
| `CoverAgent` | Generate cover direction, elements, style, cover prompt, and negative prompt. |
| `StorySetupAgent` | Generate MiniBible and initial story setup. |
| `EditorAgent` | Control commercial direction, target reader, reader promise, and style constraints. |
| `WorldviewAgent` | Maintain world rules, factions, resources, and consistency boundaries. |
| `MacroEnvironmentAgent` | Track macro environment, public sentiment, and protagonist impact scope. |
| `PowerSystemAgent` | Maintain gold-finger rules, limits, costs, upgrades, and forbidden uses. |
| `CharacterAgent` | Maintain protagonist, supporting cast, antagonists, relationships, and behavioral boundaries. |
| `ForeshadowingAgent` | Track foreshadowing items, payoff plans, and unresolved hooks. |
| `ChapterPlannerAgent` | Generate ChapterBriefs with hook, goal, conflict, payoff, and ending hook. |
| `ChapterWriterAgent` | Generate chapter drafts from MiniBible, Agent state, and ChapterBrief. |
| `StyleAgent` | Apply platform-oriented style and pacing polish. |
| `AntiAIFlavorAgent` | Reduce formulaic or AI-like phrasing and add concrete scene details. |
| `ReviewAgent` | Review generated artifacts and return pass/revise/reject reports. |
| `RewriteAgent` | Execute revision tasks using must_keep, must_change, and do_not_change constraints. |

## Agent state model

Every Agent state is stored in `AgentStates`.

Core fields:

- `agent_state_id`
- `agent_id`
- `book_id`
- `status`
- `current_state`
- `memory_summary`
- `locked_rules`
- `open_questions`
- `last_input_ref`
- `last_output_ref`
- `last_seen_chapter`
- `risk_flags`
- `updated_at`

## Per-book Agent Team

Every book has a logical Agent Team. In v0.1, all teams use the shared `AgentStates` table with `book_id` filtering.

This avoids creating one physical table per book while still allowing the UI to display a dedicated Agent Team panel for each book.

## Agent Team snapshot

Before chapter generation, the backend creates an `AgentTeamSnapshot`.

The snapshot freezes:

- Editor state.
- Worldview state.
- Macro environment state.
- Power system state.
- Character state.
- Foreshadowing state.
- Style constraints.

Each `ChapterVersion` links to the snapshot used to generate it.

This enables tracing why a chapter was written a certain way and prevents silent drift in long-form generation.
