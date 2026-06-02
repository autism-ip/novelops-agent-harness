"""
[INPUT]: 依赖 app.feishu.client.FeishuClient 与 _TOKEN_INVALID_CODES
[OUTPUT]: 对外提供 token-invalid 重试行为级测试
[POS]: tests 的 token 重试门禁，验证 99991663/99991668 触发清 token + 重试
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.feishu.client import FeishuAPIError, FeishuClient


# ============================================================
# helpers
# ============================================================


def _make_client() -> FeishuClient:
    return FeishuClient(app_id="id", app_secret="secret")


def _mock_auth(mock_http: MagicMock) -> None:
    auth_resp = MagicMock()
    auth_resp.status_code = 200
    auth_resp.json.return_value = {
        "code": 0,
        "tenant_access_token": "tok",
        "expire": 7200,
    }
    auth_resp.raise_for_status = MagicMock()
    mock_http.post.return_value = auth_resp


# ============================================================
# token-invalid retry
# ============================================================


class TestTokenInvalidRetry:
    """FeishuClient retries once on token-invalid business codes."""

    @pytest.mark.parametrize("biz_code", [99991663, 99991668])
    @patch("app.feishu.client.httpx.Client")
    def test_retries_on_token_invalid(
        self, mock_cls: MagicMock, biz_code: int
    ) -> None:
        """Token-invalid codes clear cache and retry once."""
        mock_http = MagicMock()
        mock_cls.return_value = mock_http
        _mock_auth(mock_http)

        # first call → token-invalid; second call → success
        fail_resp = MagicMock()
        fail_resp.status_code = 200
        fail_resp.json.return_value = {"code": biz_code, "msg": "token bad"}

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"code": 0, "data": "ok"}

        mock_http.request.side_effect = [fail_resp, ok_resp]

        client = _make_client()
        result = client.get("/test")

        assert result == {"code": 0, "data": "ok"}
        assert mock_http.request.call_count == 2

    @patch("app.feishu.client.httpx.Client")
    def test_no_retry_on_other_codes(self, mock_cls: MagicMock) -> None:
        """Non-token-invalid codes raise immediately."""
        mock_http = MagicMock()
        mock_cls.return_value = mock_http
        _mock_auth(mock_http)

        err_resp = MagicMock()
        err_resp.status_code = 200
        err_resp.json.return_value = {"code": 99999, "msg": "other error"}

        mock_http.request.return_value = err_resp

        client = _make_client()
        with pytest.raises(FeishuAPIError, match="code=99999"):
            client.get("/test")

        assert mock_http.request.call_count == 1
