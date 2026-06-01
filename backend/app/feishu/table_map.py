"""
[INPUT]: 依赖 os.environ 的 FEISHU_APP_TOKEN 与 FEISHU_TABLE_ID_* 覆盖变量
[OUTPUT]: 对外提供 TABLE_NAMES、FIELD_MAPS、TableMapConfig
[POS]: feishu 的配置中枢，被 repo 层与 pipeline 层消费，定义全部 16 张表的名称与字段映射
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# TABLE_NAMES — logical snake_case key → Feishu Bitable display name
# ---------------------------------------------------------------------------

TABLE_NAMES: dict[str, str] = {
    "agents":               "Agents",
    "agent_states":         "AgentStates",
    "agent_runs":           "AgentRuns",
    "pipeline_runs":        "PipelineRuns",
    "step_runs":            "StepRuns",
    "hotspots":             "Hotspots",
    "hotspot_analyses":     "HotspotAnalyses",
    "title_candidates":     "TitleCandidates",
    "cover_plans":          "CoverPlans",
    "books":                "Books",
    "chapter_briefs":       "ChapterBriefs",
    "chapter_versions":     "ChapterVersions",
    "review_reports":       "ReviewReports",
    "revision_tasks":       "RevisionTasks",
    "agent_team_snapshots": "AgentTeamSnapshots",
    "approval_events":      "ApprovalEvents",
}

# ---------------------------------------------------------------------------
# FIELD_MAPS — logical table name → {python_field: feishu_field}
# All 16 tables; python name equals feishu name in every case.
# ---------------------------------------------------------------------------

FIELD_MAPS: dict[str, dict[str, str]] = {
    "agents": {
        "agent_id":        "agent_id",
        "agent_name":      "agent_name",
        "agent_role":      "agent_role",
        "scope":           "scope",
        "enabled":         "enabled",
        "model_provider":  "model_provider",
        "model_name":      "model_name",
        "prompt_version":  "prompt_version",
        "input_schema":    "input_schema",
        "output_schema":   "output_schema",
        "tools_allowed":   "tools_allowed",
        "description":     "description",
    },
    "agent_states": {
        "agent_state_id":    "agent_state_id",
        "agent_id":          "agent_id",
        "book_id":           "book_id",
        "status":            "status",
        "current_state":     "current_state",
        "memory_summary":    "memory_summary",
        "locked_rules":      "locked_rules",
        "open_questions":    "open_questions",
        "last_input_ref":    "last_input_ref",
        "last_output_ref":   "last_output_ref",
        "last_seen_chapter": "last_seen_chapter",
        "risk_flags":        "risk_flags",
        "updated_at":        "updated_at",
    },
    "agent_runs": {
        "agent_run_id":    "agent_run_id",
        "agent_id":        "agent_id",
        "pipeline_run_id": "pipeline_run_id",
        "step_run_id":     "step_run_id",
        "book_id":         "book_id",
        "input_refs":      "input_refs",
        "output_refs":     "output_refs",
        "model":           "model",
        "prompt_version":  "prompt_version",
        "status":          "status",
        "error_message":   "error_message",
        "started_at":      "started_at",
        "finished_at":     "finished_at",
    },
    "pipeline_runs": {
        "pipeline_run_id":   "pipeline_run_id",
        "pipeline_type":     "pipeline_type",
        "status":            "status",
        "current_step":      "current_step",
        "source_hotspot_id": "source_hotspot_id",
        "book_id":           "book_id",
        "operator":          "operator",
        "created_at":        "created_at",
        "updated_at":        "updated_at",
        "error_message":     "error_message",
    },
    "step_runs": {
        "step_run_id":       "step_run_id",
        "pipeline_run_id":   "pipeline_run_id",
        "step_key":          "step_key",
        "assigned_agent_id": "assigned_agent_id",
        "depends_on":        "depends_on",
        "status":            "status",
        "input_refs":        "input_refs",
        "output_refs":       "output_refs",
        "lease_owner":       "lease_owner",
        "lease_until":       "lease_until",
        "retry_count":       "retry_count",
        "error_message":     "error_message",
        "started_at":        "started_at",
        "finished_at":       "finished_at",
    },
    "hotspots": {
        "hotspot_id":  "hotspot_id",
        "source":      "source",
        "rank":        "rank",
        "title":       "title",
        "url":         "url",
        "heat_value":  "heat_value",
        "category":    "category",
        "captured_at": "captured_at",
        "raw_json":    "raw_json",
        "dedupe_hash": "dedupe_hash",
        "status":      "status",
    },
    "hotspot_analyses": {
        "analysis_id":         "analysis_id",
        "hotspot_id":          "hotspot_id",
        "summary":             "summary",
        "core_emotions":       "core_emotions",
        "hit_patterns":        "hit_patterns",
        "novel_genres":        "novel_genres",
        "novelization_angles": "novelization_angles",
        "reader_promise":      "reader_promise",
        "risk_level":          "risk_level",
        "risk_notes":          "risk_notes",
        "writability_score":   "writability_score",
        "approval_status":     "approval_status",
    },
    "title_candidates": {
        "title_id":        "title_id",
        "analysis_id":     "analysis_id",
        "title":           "title",
        "hook":            "hook",
        "selling_point":   "selling_point",
        "click_score":     "click_score",
        "genre_fit_score": "genre_fit_score",
        "risk_notes":      "risk_notes",
        "approval_status": "approval_status",
    },
    "cover_plans": {
        "cover_id":        "cover_id",
        "title_id":        "title_id",
        "visual_direction":"visual_direction",
        "main_elements":   "main_elements",
        "style":           "style",
        "cover_prompt":    "cover_prompt",
        "negative_prompt": "negative_prompt",
        "cover_asset_url": "cover_asset_url",
        "approval_status": "approval_status",
    },
    "books": {
        "book_id":    "book_id",
        "hotspot_id": "hotspot_id",
        "analysis_id":"analysis_id",
        "title_id":   "title_id",
        "cover_id":   "cover_id",
        "book_title": "book_title",
        "genre":      "genre",
        "status":     "status",
        "mini_bible": "mini_bible",
        "created_at": "created_at",
    },
    "chapter_briefs": {
        "brief_id":        "brief_id",
        "book_id":         "book_id",
        "chapter_no":      "chapter_no",
        "chapter_title":   "chapter_title",
        "opening_hook":    "opening_hook",
        "scene_goal":      "scene_goal",
        "conflict":        "conflict",
        "payoff":          "payoff",
        "ending_hook":     "ending_hook",
        "approval_status": "approval_status",
    },
    "chapter_versions": {
        "version_id":             "version_id",
        "book_id":                "book_id",
        "chapter_no":             "chapter_no",
        "version_no":             "version_no",
        "chapter_title":          "chapter_title",
        "content":                "content",
        "status":                 "status",
        "agent_team_snapshot_id": "agent_team_snapshot_id",
        "review_report_id":       "review_report_id",
        "prompt_version":         "prompt_version",
        "created_at":             "created_at",
    },
    "review_reports": {
        "review_id":      "review_id",
        "target_type":    "target_type",
        "target_id":      "target_id",
        "reviewer_agent": "reviewer_agent",
        "scores":         "scores",
        "problems":       "problems",
        "suggestions":    "suggestions",
        "overall_status": "overall_status",
        "created_at":     "created_at",
    },
    "revision_tasks": {
        "revision_task_id":  "revision_task_id",
        "target_type":       "target_type",
        "target_id":         "target_id",
        "from_version_id":   "from_version_id",
        "revision_type":     "revision_type",
        "reason":            "reason",
        "must_keep":         "must_keep",
        "must_change":       "must_change",
        "do_not_change":     "do_not_change",
        "assigned_agent_id": "assigned_agent_id",
        "status":            "status",
        "created_at":        "created_at",
    },
    "agent_team_snapshots": {
        "snapshot_id":          "snapshot_id",
        "book_id":              "book_id",
        "chapter_no":           "chapter_no",
        "agent_states_json":    "agent_states_json",
        "used_by_version_id":   "used_by_version_id",
        "created_at":           "created_at",
    },
    "approval_events": {
        "approval_id": "approval_id",
        "target_type": "target_type",
        "target_id":   "target_id",
        "action":      "action",
        "operator":    "operator",
        "comment":     "comment",
        "created_at":  "created_at",
    },
}


# ---------------------------------------------------------------------------
# TableMapConfig — runtime configuration for Feishu Bitable access
# ---------------------------------------------------------------------------

class TableMapConfig:
    """Runtime config: app token + table-ID resolution.

    Table IDs are resolved in priority order:
      1. Environment variable ``FEISHU_TABLE_ID_<UPPER_SNAKE>``.
      2. Fallback: the logical name itself (placeholder until deploy-time wiring).
    """

    def __init__(self, app_token: str | None = None) -> None:
        self.app_token: str = app_token or os.environ.get("FEISHU_APP_TOKEN", "")

    # --- table-ID resolution ---------------------------------------------------

    def get_table_id(self, name: str) -> str:
        """Return the Feishu Bitable table-ID for *name*.

        Checks ``FEISHU_TABLE_ID_<NAME_UPPER>`` first; falls back to *name*
        itself as a deploy-time placeholder.
        """
        env_key = f"FEISHU_TABLE_ID_{name.upper()}"
        return os.environ.get(env_key, name)

    # --- field-map access ------------------------------------------------------

    def get_field_map(self, name: str) -> dict[str, str]:
        """Return the {python_field: feishu_field} mapping for table *name*."""
        try:
            return FIELD_MAPS[name]
        except KeyError:
            raise KeyError(
                f"Unknown table '{name}'. Valid names: {sorted(FIELD_MAPS)}"
            ) from None
