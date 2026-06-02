# app/feishu/repositories/
> L2 | 父级: ../CLAUDE.md

成员清单
__init__.py: 包入口，重导出全部 16 个具体 Repo 类与 create_repositories 工厂函数。
base.py: 通用 Bitable CRUD 基类，提供 create/get/list/update/delete + _field_filter + find_by_business_key，自动字段映射与分页。
factory.py: 组装工厂，一次性创建全部 16 个 repository 实例，返回 {table_name: repo} 字典。
agents.py: AgentsRepo，find_by_role 查询。
agent_states.py: AgentStatesRepo，find_by_agent/find_by_status 查询。
agent_runs.py: AgentRunsRepo，find_by_agent/find_by_pipeline 查询。
pipeline_runs.py: PipelineRunsRepo，find_by_status/find_by_type 查询。
step_runs.py: StepRunsRepo，find_by_pipeline/claim_step 查询。
hotspots.py: HotspotsRepo，find_by_status/find_by_dedupe_hash 查询。
hotspot_analyses.py: HotspotAnalysesRepo，find_by_hotspot 查询。
title_candidates.py: TitleCandidatesRepo，find_by_analysis 查询。
cover_plans.py: CoverPlansRepo，find_by_title 查询。
books.py: BooksRepo，find_by_status 查询。
chapter_briefs.py: ChapterBriefsRepo，find_by_book 查询。
chapter_versions.py: ChapterVersionsRepo，find_by_chapter 查询（复合条件 book_id + chapter_no）。
review_reports.py: ReviewReportsRepo，find_by_target 查询（复合条件 target_type + target_id）。
revision_tasks.py: RevisionTasksRepo，find_by_status 查询。
agent_team_snapshots.py: AgentTeamSnapshotsRepo，find_by_chapter 查询（复合条件 book_id + chapter_no）。
approval_events.py: ApprovalEventsRepo，find_by_target 查询（复合条件 target_type + target_id）。

架构决策
每个 Repo 继承 BaseRepository，在 __init__ 中通过 FIELD_MAPS[table_key] 注入字段映射。领域查询方法使用 Feishu Bitable filter 语法（CurrentValue.[field] = "value"）。工厂模式统一创建，支持环境变量覆盖表 ID。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
