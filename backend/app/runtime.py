"""Production composition. All v0.2 machine mutations share one kernel."""
from pathlib import Path
import json

from app.feishu.client import FeishuClient
from app.feishu.repositories.base import BaseRepository
from app.feishu.table_map import FIELD_MAPS, TableMapConfig
from app.harness import HarnessKernel
from app.storage import FeishuStorageProvider


def build_runtime(settings):
    if settings.RESEARCH_ENABLED and not (settings.GENERATION_ENABLED and (settings.HOTSPOTS_ENABLED or settings.OPENCLI_ENABLED)):
        raise ValueError("RESEARCH_ENABLED requires GENERATION_ENABLED and HOTSPOTS_ENABLED or OPENCLI_ENABLED")
    if settings.CREATIVE_ENABLED and not settings.RESEARCH_ENABLED:
        raise ValueError("CREATIVE_ENABLED requires RESEARCH_ENABLED")
    config = TableMapConfig()
    if not config.app_token:
        raise ValueError("FEISHU_APP_TOKEN is required when HARNESS_ENABLED=true")
    client = FeishuClient(settings.FEISHU_APP_ID, settings.FEISHU_APP_SECRET)
    try:
        names = ("pipeline_runs", "step_runs", "approval_events")
        if settings.OPENCLI_ENABLED:
            if not settings.OPENCLI_DOUYIN_COMMAND or any(not s.strip() for s in settings.OPENCLI_DOUYIN_COMMAND):
                raise ValueError("OPENCLI_DOUYIN_COMMAND must contain the installed public-feed command arguments")
        if settings.HOTSPOTS_ENABLED or settings.OPENCLI_ENABLED:
            names += ("hotspots",)
        if settings.GENERATION_ENABLED or settings.OPENCLI_ENABLED:
            names += ("traces",)
        if settings.GENERATION_ENABLED:
            names += ("artifacts",)
        if settings.RESEARCH_ENABLED:
            names += ("hotspot_analyses",)
        if settings.CREATIVE_ENABLED:
            names += ("title_candidates", "cover_plans")
        repositories = {name: BaseRepository(client, config.app_token, config.get_table_id(name), FIELD_MAPS[name])
                        for name in names}
        storage = FeishuStorageProvider(repositories, {name: next(iter(FIELD_MAPS[name])) for name in names})
        kernel = HarnessKernel(storage, journal_dir=Path(settings.HARNESS_JOURNAL_DIR),
            poll_interval=settings.HARNESS_POLL_INTERVAL, max_retries=settings.HARNESS_MAX_RETRIES)
        if settings.GENERATION_ENABLED or settings.OPENCLI_ENABLED:
            from app.generation import TraceRecorder
            kernel.telemetry = TraceRecorder(kernel)
        if settings.HOTSPOTS_ENABLED or settings.OPENCLI_ENABLED:
            from app.hotspots import HotspotService
            from app.tools.adapters.douyin_hotspots import DouyinHotspotAdapter
            from app.tools.runner import OpenCLIRunner
            kernel.hotspots = HotspotService(kernel, DouyinHotspotAdapter(
                OpenCLIRunner(settings.opencli_bin, settings.opencli_timeout), settings, settings.OPENCLI_DOUYIN_COMMAND),
                collection_enabled=settings.OPENCLI_ENABLED)
        if settings.GENERATION_ENABLED:
            from app.generation import ArtifactStore, ChatProvider, ModelRouter, Route, SemanticRuntime
            routes = {name: Route.model_validate(value) for name, value in json.loads(settings.MODEL_ROUTES_JSON).items()}
            kernel.artifacts = ArtifactStore(kernel)
            kernel.model_router = ModelRouter(routes, {
                "openai": ChatProvider("openai", settings.OPENAI_API_KEY),
                "deepseek": ChatProvider("deepseek", settings.DEEPSEEK_API_KEY)}, kernel.telemetry)
            kernel.semantic = SemanticRuntime(kernel.model_router, kernel.artifacts)
        if settings.RESEARCH_ENABLED:
            from app.research import ResearchService
            kernel.research = ResearchService(kernel, selection_required=settings.RESEARCH_SELECTION_REQUIRED)
        if settings.CREATIVE_ENABLED:
            from app.creative import CreativeService
            kernel.creative = CreativeService(kernel)
        return kernel, client
    except Exception:
        if "kernel" in locals() and getattr(kernel, "model_router", None):
            kernel.model_router.close()
        client._http.close()
        raise
