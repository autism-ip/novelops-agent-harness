"""Production composition. All v0.2 machine mutations share one kernel."""
from pathlib import Path

from app.feishu.client import FeishuClient
from app.feishu.repositories.base import BaseRepository
from app.feishu.table_map import FIELD_MAPS, TableMapConfig
from app.harness import HarnessKernel
from app.storage import FeishuStorageProvider


def build_runtime(settings):
    config = TableMapConfig()
    if not config.app_token:
        raise ValueError("FEISHU_APP_TOKEN is required when HARNESS_ENABLED=true")
    client = FeishuClient(settings.FEISHU_APP_ID, settings.FEISHU_APP_SECRET)
    try:
        names = ("pipeline_runs", "step_runs", "approval_events")
        repositories = {name: BaseRepository(client, config.app_token, config.get_table_id(name), FIELD_MAPS[name])
                        for name in names}
        storage = FeishuStorageProvider(repositories, {name: next(iter(FIELD_MAPS[name])) for name in names})
        kernel = HarnessKernel(storage, journal_dir=Path(settings.HARNESS_JOURNAL_DIR),
            poll_interval=settings.HARNESS_POLL_INTERVAL, max_retries=settings.HARNESS_MAX_RETRIES)
        return kernel, client
    except Exception:
        client._http.close()
        raise
