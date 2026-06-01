"""Feishu Bitable repository layer — generic CRUD + domain queries."""

from app.feishu.repositories.agent_runs import AgentRunsRepo
from app.feishu.repositories.agent_states import AgentStatesRepo
from app.feishu.repositories.agent_team_snapshots import AgentTeamSnapshotsRepo
from app.feishu.repositories.agents import AgentsRepo
from app.feishu.repositories.approval_events import ApprovalEventsRepo
from app.feishu.repositories.base import BaseRepository
from app.feishu.repositories.books import BooksRepo
from app.feishu.repositories.chapter_briefs import ChapterBriefsRepo
from app.feishu.repositories.chapter_versions import ChapterVersionsRepo
from app.feishu.repositories.cover_plans import CoverPlansRepo
from app.feishu.repositories.factory import create_repositories
from app.feishu.repositories.hotspot_analyses import HotspotAnalysesRepo
from app.feishu.repositories.hotspots import HotspotsRepo
from app.feishu.repositories.pipeline_runs import PipelineRunsRepo
from app.feishu.repositories.review_reports import ReviewReportsRepo
from app.feishu.repositories.revision_tasks import RevisionTasksRepo
from app.feishu.repositories.step_runs import StepRunsRepo
from app.feishu.repositories.title_candidates import TitleCandidatesRepo

__all__ = [
    "AgentsRepo",
    "AgentStatesRepo",
    "AgentRunsRepo",
    "PipelineRunsRepo",
    "StepRunsRepo",
    "HotspotsRepo",
    "HotspotAnalysesRepo",
    "TitleCandidatesRepo",
    "CoverPlansRepo",
    "BooksRepo",
    "ChapterBriefsRepo",
    "ChapterVersionsRepo",
    "ReviewReportsRepo",
    "RevisionTasksRepo",
    "AgentTeamSnapshotsRepo",
    "ApprovalEventsRepo",
    "BaseRepository",
    "create_repositories",
]
