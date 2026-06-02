"""
schemas — DouyinHotspotRecord frozen dataclass.

[INPUT]: 无外部依赖，纯数据定义
[OUTPUT]: DouyinHotspotRecord frozen dataclass
[POS]: tools 包的数据契约层，被 adapters 消费，映射飞书 Hotspots 表
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DouyinHotspotRecord:
    """Normalized Douyin hotspot entry — maps 1:1 to Feishu Hotspots table.

    Frozen: no mutation after construction. raw_json excluded from hash
    computation because dict is unhashable.
    """

    source: str             # "douyin"
    rank: int               # 1-based ranking
    title: str              # hotspot title
    url: str                # source URL (may be empty)
    heat_value: int         # numeric heat value
    category: str           # category label (may be empty)
    captured_at: str        # ISO 8601 UTC timestamp
    raw_json: dict = field(hash=False)  # original record, preserved for audit
    dedupe_hash: str = ""   # sha256(source:title:url)
    hotspot_id: str = ""    # uuid4
