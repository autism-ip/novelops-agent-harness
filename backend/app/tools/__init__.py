"""
tools — OpenCLI integration package.

[INPUT]: 依赖 app.config.Settings (OPENCLI_ENABLED, OPENCLI_BIN, OPENCLI_TIMEOUT)
[OUTPUT]: OpenCLIRunner, OpenCLIResult, DouyinHotspotAdapter, DouyinAdapterResult, error classes, DouyinHotspotRecord
[POS]: backend 的外部工具集成层，通过子进程隔离调用 OpenCLI
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from app.tools.adapters import DouyinAdapterResult, DouyinHotspotAdapter
from app.tools.errors import (
    OpenCLIError,
    OpenCLIExitError,
    OpenCLIOutputError,
    OpenCLITimeoutError,
)
from app.tools.runner import OpenCLIRunner, OpenCLIResult
from app.tools.schemas import DouyinHotspotRecord

__all__ = [
    "DouyinAdapterResult",
    "DouyinHotspotAdapter",
    "DouyinHotspotRecord",
    "OpenCLIError",
    "OpenCLIExitError",
    "OpenCLIOutputError",
    "OpenCLIRunner",
    "OpenCLIResult",
    "OpenCLITimeoutError",
]
