"""
[INPUT]: 依赖 app.feishu.client 的 FeishuClient、FeishuAuthError、FeishuAPIError
[OUTPUT]: 对外提供 FeishuClient 的行为级测试用例——token 生命周期、请求注入、401 重试、异常路径
[POS]: tests 的飞书客户端门禁，验证认证与请求重试的外部行为契约
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.feishu.client import FeishuAPIError, FeishuAuthError, FeishuClient


# ============================================================
# helpers
# ============================================================


def _make_client(app_id: str = "id-ok", app_secret: str = "secret-ok") -> FeishuClient:
    """Build a FeishuClient without spawning a real httpx transport."""
    return FeishuClient(app_id=app_id, app_secret=app_secret)


def _mock_post_response(
    json_data: dict, status_code: int = 200
) -> MagicMock:
    """Return a mock httpx.Response for a POST call."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    resp.text = str(json_data)
    return resp


def _mock_data_response(
    data: dict, status_code: int = 200
) -> MagicMock:
    """Return a mock httpx.Response wrapping a standard Feishu envelope."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = {"code": 0, "data": data}
    resp.raise_for_status.return_value = None
    resp.text = str(data)
    return resp


# ============================================================
# token acquisition
# ============================================================


class TestTokenAcquisition:
    """_refresh_token fetches and caches tenant_access_token."""

    @patch("app.feishu.client.httpx.Client")
    def test_refresh_token_success(self, mock_http_cls: MagicMock) -> None:
        """Token is stored after a successful auth POST."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        client = FeishuClient(app_id="id", app_secret="sec")

        auth_resp = _mock_post_response(
            {"code": 0, "tenant_access_token": "t-abc", "expire": 7200}
        )
        mock_http.post.return_value = auth_resp

        token = client._refresh_token()

        assert token == "t-abc"
        assert client._token == "t-abc"
        mock_http.post.assert_called_once()

    @patch("app.feishu.client.httpx.Client")
    def test_get_valid_token_caches(self, mock_http_cls: MagicMock) -> None:
        """Second call reuses cached token without re-auth."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        client = FeishuClient(app_id="id", app_secret="sec")

        auth_resp = _mock_post_response(
            {"code": 0, "tenant_access_token": "t-xyz", "expire": 7200}
        )
        mock_http.post.return_value = auth_resp

        first = client._get_valid_token()
        second = client._get_valid_token()

        assert first == second == "t-xyz"
        # auth POST called once — token cached for second call
        assert mock_http.post.call_count == 1


# ============================================================
# token attachment
# ============================================================


class TestTokenAttachment:
    """Every request carries Authorization: Bearer {token}."""

    @patch("app.feishu.client.httpx.Client")
    def test_request_includes_bearer_header(
        self, mock_http_cls: MagicMock
    ) -> None:
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        client = FeishuClient(app_id="id", app_secret="sec")

        # auth call uses self._http.post
        auth_resp = _mock_post_response(
            {"code": 0, "tenant_access_token": "t-777", "expire": 7200}
        )
        mock_http.post.return_value = auth_resp

        # data call uses self._http.request (via _request method)
        data_resp = _mock_data_response({"record": {"id": "r1"}})
        mock_http.request.return_value = data_resp

        result = client.post("/bitable/v1/test", body={"k": "v"})

        # verify Bearer header on the request call
        data_call = mock_http.request.call_args
        headers = data_call.kwargs.get("headers", {})
        assert headers["Authorization"] == "Bearer t-777"
        assert result == {"code": 0, "data": {"record": {"id": "r1"}}}


# ============================================================
# 401 retry
# ============================================================


class TestRetryOn401:
    """A 401 response triggers token clear + single retry."""

    @patch("app.feishu.client.httpx.Client")
    def test_retry_succeeds_after_401(self, mock_http_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        client = FeishuClient(app_id="id", app_secret="sec")

        auth_ok = _mock_post_response(
            {"code": 0, "tenant_access_token": "t-old", "expire": 7200}
        )
        resp_401 = MagicMock(spec=httpx.Response)
        resp_401.status_code = 401
        resp_401.text = "Unauthorized"

        auth_refresh = _mock_post_response(
            {"code": 0, "tenant_access_token": "t-new", "expire": 7200}
        )
        resp_ok = _mock_data_response({"record": {"id": "r2"}})

        mock_http.post.side_effect = [auth_ok, auth_refresh]
        mock_http.request.side_effect = [resp_401, resp_ok]

        result = client.get("/bitable/v1/apps/app/tables/tbl/records/rec1")

        assert result == {"code": 0, "data": {"record": {"id": "r2"}}}
        assert client._token == "t-new"

    @patch("app.feishu.client.httpx.Client")
    def test_retry_fails_raises_auth_error(self, mock_http_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        client = FeishuClient(app_id="id", app_secret="sec")

        auth_ok = _mock_post_response(
            {"code": 0, "tenant_access_token": "t-old", "expire": 7200}
        )
        auth_refresh = _mock_post_response(
            {"code": 0, "tenant_access_token": "t-new", "expire": 7200}
        )

        resp_401 = MagicMock(spec=httpx.Response)
        resp_401.status_code = 401
        resp_401.text = "Unauthorized"

        mock_http.post.side_effect = [auth_ok, auth_refresh]
        mock_http.request.side_effect = [resp_401, resp_401]

        with pytest.raises(FeishuAuthError, match="Auth failed after retry"):
            client.get("/bitable/v1/test")


# ============================================================
# auth error paths
# ============================================================


class TestAuthErrors:
    """Construction and token refresh failure paths."""

    def test_empty_app_id_raises(self) -> None:
        with pytest.raises(FeishuAuthError, match="non-empty"):
            FeishuClient(app_id="", app_secret="sec")

    def test_empty_app_secret_raises(self) -> None:
        with pytest.raises(FeishuAuthError, match="non-empty"):
            FeishuClient(app_id="id", app_secret="")

    @patch("app.feishu.client.httpx.Client")
    def test_business_error_code_nonzero(self, mock_http_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        client = FeishuClient(app_id="id", app_secret="sec")

        bad_resp = _mock_post_response(
            {"code": 10003, "msg": "invalid app_id"}
        )
        mock_http.post.return_value = bad_resp

        with pytest.raises(FeishuAuthError, match="Token endpoint error"):
            client._refresh_token()

    @patch("app.feishu.client.httpx.Client")
    def test_no_token_in_response(self, mock_http_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        client = FeishuClient(app_id="id", app_secret="sec")

        empty_resp = _mock_post_response({"code": 0, "expire": 7200})
        mock_http.post.return_value = empty_resp

        with pytest.raises(FeishuAuthError, match="No token in response"):
            client._refresh_token()

    @patch("app.feishu.client.httpx.Client")
    def test_business_error_in_data_response(
        self, mock_http_cls: MagicMock
    ) -> None:
        """Response 200 but business code != 0 raises FeishuAuthError."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        client = FeishuClient(app_id="id", app_secret="sec")

        auth_resp = _mock_post_response(
            {"code": 0, "tenant_access_token": "t-err", "expire": 7200}
        )
        err_resp = MagicMock(spec=httpx.Response)
        err_resp.status_code = 200
        err_resp.json.return_value = {"code": 99999, "msg": "server boom"}
        err_resp.text = "server boom"

        mock_http.post.return_value = auth_resp
        mock_http.request.return_value = err_resp

        with pytest.raises(FeishuAuthError, match="code=99999"):
            client.get("/bitable/v1/test")


# ============================================================
# HTTP verbs
# ============================================================


class TestHttpVerbs:
    """Public verb methods delegate to _request correctly."""

    @patch("app.feishu.client.httpx.Client")
    def test_get_delegates_to_request(self, mock_http_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        client = FeishuClient(app_id="id", app_secret="sec")

        auth_resp = _mock_post_response(
            {"code": 0, "tenant_access_token": "t-v", "expire": 7200}
        )
        data_resp = _mock_data_response({"items": []})
        mock_http.post.return_value = auth_resp
        mock_http.request.return_value = data_resp

        client.get("/some/path", params={"key": "val"})

        call = mock_http.request.call_args
        assert call[0][0] == "GET"
        assert call[0][1].endswith("/some/path")
        assert call.kwargs["params"] == {"key": "val"}

    @patch("app.feishu.client.httpx.Client")
    def test_put_delegates_to_request(self, mock_http_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        client = FeishuClient(app_id="id", app_secret="sec")

        auth_resp = _mock_post_response(
            {"code": 0, "tenant_access_token": "t-v", "expire": 7200}
        )
        data_resp = _mock_data_response({"record": {}})
        mock_http.post.return_value = auth_resp
        mock_http.request.return_value = data_resp

        client.put("/some/path", body={"field": "val"})

        call = mock_http.request.call_args
        assert call[0][0] == "PUT"

    @patch("app.feishu.client.httpx.Client")
    def test_delete_delegates_to_request(self, mock_http_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        client = FeishuClient(app_id="id", app_secret="sec")

        auth_resp = _mock_post_response(
            {"code": 0, "tenant_access_token": "t-v", "expire": 7200}
        )
        data_resp = _mock_data_response({})
        mock_http.post.return_value = auth_resp
        mock_http.request.return_value = data_resp

        client.delete("/some/path")

        call = mock_http.request.call_args
        assert call[0][0] == "DELETE"


# ============================================================
# HTTP error classification
# ============================================================


class TestHttpErrors:
    """Non-401 HTTP errors and transport failures raise FeishuAPIError."""

    @patch("app.feishu.client.httpx.Client")
    def test_http_4xx_raises_api_error(self, mock_http_cls: MagicMock) -> None:
        """403 (non-401) raises FeishuAPIError with status code, not FeishuAuthError."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        client = FeishuClient(app_id="id", app_secret="sec")

        auth_resp = _mock_post_response(
            {"code": 0, "tenant_access_token": "t-403", "expire": 7200}
        )
        resp_403 = MagicMock(spec=httpx.Response)
        resp_403.status_code = 403
        resp_403.text = "Forbidden"

        mock_http.post.return_value = auth_resp
        mock_http.request.return_value = resp_403

        with pytest.raises(FeishuAPIError, match="HTTP 403") as exc_info:
            client.get("/bitable/v1/test")

        assert exc_info.value.code == 403

    @patch("app.feishu.client.httpx.Client")
    def test_transport_error_raises_api_error(self, mock_http_cls: MagicMock) -> None:
        """Network failure raises FeishuAPIError (code=0), not FeishuAuthError."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        client = FeishuClient(app_id="id", app_secret="sec")

        auth_resp = _mock_post_response(
            {"code": 0, "tenant_access_token": "t-net", "expire": 7200}
        )
        mock_http.post.return_value = auth_resp
        mock_http.request.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(FeishuAPIError, match="Transport error") as exc_info:
            client.get("/bitable/v1/test")

        assert exc_info.value.code == 0

    @patch("app.feishu.client.httpx.Client")
    def test_401_still_raises_auth_error(self, mock_http_cls: MagicMock) -> None:
        """401 path still raises FeishuAuthError — existing behavior preserved."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        client = FeishuClient(app_id="id", app_secret="sec")

        auth_ok = _mock_post_response(
            {"code": 0, "tenant_access_token": "t-auth", "expire": 7200}
        )
        auth_refresh = _mock_post_response(
            {"code": 0, "tenant_access_token": "t-new", "expire": 7200}
        )

        resp_401 = MagicMock(spec=httpx.Response)
        resp_401.status_code = 401
        resp_401.text = "Unauthorized"

        mock_http.post.side_effect = [auth_ok, auth_refresh]
        mock_http.request.side_effect = [resp_401, resp_401]

        with pytest.raises(FeishuAuthError, match="Auth failed after retry"):
            client.get("/bitable/v1/test")
