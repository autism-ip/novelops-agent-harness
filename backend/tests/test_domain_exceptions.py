"""
[INPUT]: 依赖 app.feishu.client 的异常类层级
[OUTPUT]: 对外提供 domain exception hierarchy 行为级测试
[POS]: tests 的异常层级门禁，验证 FeishuError 家族的继承关系
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from app.feishu.client import (
    FeishuAPIError,
    FeishuAuthError,
    FeishuError,
    FeishuNotFoundError,
)


# ============================================================
# exception hierarchy
# ============================================================


class TestExceptionHierarchy:
    """All domain exceptions inherit from FeishuError."""

    def test_auth_error_is_feishu_error(self) -> None:
        assert issubclass(FeishuAuthError, FeishuError)

    def test_not_found_error_is_feishu_error(self) -> None:
        assert issubclass(FeishuNotFoundError, FeishuError)

    def test_api_error_is_feishu_error(self) -> None:
        assert issubclass(FeishuAPIError, FeishuError)

    def test_feishu_error_is_exception(self) -> None:
        assert issubclass(FeishuError, Exception)

    def test_not_found_error_has_code(self) -> None:
        err = FeishuNotFoundError("not found", code=1254043)
        assert err.code == 1254043
        assert str(err) == "not found"

    def test_api_error_has_code(self) -> None:
        err = FeishuAPIError("bad request", code=99999)
        assert err.code == 99999
        assert str(err) == "bad request"
