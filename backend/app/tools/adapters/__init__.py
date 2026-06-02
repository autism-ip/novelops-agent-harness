"""
adapters — Tool-specific adapters for external CLI integrations.

[INPUT]: 依赖 runner 模块的 OpenCLIRunner
[OUTPUT]: DouyinHotspotAdapter, DouyinAdapterResult (re-exported from douyin_hotspots)
[POS]: tools.adapters 子包，每个 adapter 封装一个外部工具的命令组装与输出归一化
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from app.tools.adapters.douyin_hotspots import DouyinAdapterResult, DouyinHotspotAdapter

__all__ = ["DouyinAdapterResult", "DouyinHotspotAdapter"]
