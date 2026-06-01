"""
[INPUT]: 依赖 app.feishu.client.FeishuClient、app.feishu.table_map.TableMapConfig，以及 16 个具体 Repo 类
[OUTPUT]: 对外提供 create_repositories 工厂函数
[POS]: repositories 包的组装工厂，一次性创建全部 16 个 repository 实例
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from app.feishu.client import FeishuClient
from app.feishu.repositories.approval_events import ApprovalEventsRepo
from app.feishu.repositories.agent_runs import AgentRunsRepo
from app.feishu.repositories.agent_states import AgentStatesRepo
from app.feishu.repositories.agent_team_snapshots import AgentTeamSnapshotsRepo
from app.feishu.repositories.agents import AgentsRepo
from app.feishu.repositories.base import BaseRepository
from app.feishu.repositories.books import BooksRepo
from app.feishu.repositories.chapter_briefs import ChapterBriefsRepo
from app.feishu.repositories.chapter_versions import ChapterVersionsRepo
from app.feishu.repositories.cover_plans import CoverPlansRepo
from app.feishu.repositories.hotspot_analyses import HotspotAnalysesRepo
from app.feishu.repositories.hotspots import HotspotsRepo
from app.feishu.repositories.pipeline_runs import PipelineRunsRepo
from app.feishu.repositories.review_reports import ReviewReportsRepo
from app.feishu.repositories.revision_tasks import RevisionTasksRepo
from app.feishu.repositories.step_runs import StepRunsRepo
from app.feishu.repositories.title_candidates import TitleCandidatesRepo
from app.feishu.table_map import TableMapConfig


# ============================================================
# repository registry
# ============================================================

_REPO_CLASSES: dict[str, type[BaseRepository]] = {
    "agents":               AgentsRepo,
    "agent_states":         AgentStatesRepo,
    "agent_runs":           AgentRunsRepo,
    "pipeline_runs":        PipelineRunsRepo,
    "step_runs":            StepRunsRepo,
    "hotspots":             HotspotsRepo,
    "hotspot_analyses":     HotspotAnalysesRepo,
    "title_candidates":     TitleCandidatesRepo,
    "cover_plans":          CoverPlansRepo,
    "books":                BooksRepo,
    "chapter_briefs":       ChapterBriefsRepo,
    "chapter_versions":     ChapterVersionsRepo,
    "review_reports":       ReviewReportsRepo,
    "revision_tasks":       RevisionTasksRepo,
    "agent_team_snapshots": AgentTeamSnapshotsRepo,
    "approval_events":      ApprovalEventsRepo,
}


# ============================================================
# factory
# ============================================================


def create_repositories(
    client: FeishuClient,
    config: TableMapConfig,
) -> dict[str, BaseRepository]:
    """Create all 16 repository instances keyed by table name.

    Args:
        client: Authenticated Feishu HTTP client.
        config: Runtime config providing app_token and table IDs.

    Returns:
        Dict mapping logical table names to repository instances.
    """
    repos: dict[str, BaseRepository] = {}

    for name, repo_cls in _REPO_CLASSES.items():
        table_id = config.get_table_id(name)
        repos[name] = repo_cls(client, config.app_token, table_id)

    return repos
