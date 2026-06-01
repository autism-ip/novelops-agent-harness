"""
[INPUT]: 依赖 httpx 的同步 HTTP 客户端，依赖 time 的 monotonic clock
[OUTPUT]: 对外提供 FeishuClient 类、FeishuAuthError 异常、FeishuAPIError 异常、FeishuNotFoundError 异常
[POS]: feishu 包的核心 HTTP 层，被 Bitable repository 消费，屏蔽飞书认证与重试细节
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

# ============================================================
# imports
# ============================================================

from __future__ import annotations

import time

import httpx


# ============================================================
# exceptions
# ============================================================


class FeishuAuthError(Exception):
    """飞书认证失败——token 获取或刷新均不可恢复。"""


class FeishuAPIError(Exception):
    """飞书 API 业务错误或 HTTP 4xx/5xx。"""

    def __init__(self, message: str, code: int = 0) -> None:
        super().__init__(message)
        self.code = code


class FeishuNotFoundError(FeishuAPIError):
    """飞书记录不存在——请求的记录 ID 未找到。"""

    def __init__(self, message: str = "not found", code: int = 1254043) -> None:
        super().__init__(message, code=code)


# ============================================================
# client
# ============================================================

# 认证端点（飞书内部应用 tenant_access_token）
_AUTH_PATH = "/auth/v3/tenant_access_token/internal"

# 提前 5 分钟视为过期，避免在请求途中 token 失效
_TOKEN_EXPIRY_BUFFER_S = 300


class FeishuClient:
    """同步飞书 HTTP 客户端。

    职责：
    - 自动获取 / 刷新 tenant_access_token
    - 为每次请求注入 Authorization header
    - 解析飞书 JSON 响应并在业务码非 0 时抛异常
    - 401 自动重试一次（先清 token 再认证）
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        base_url: str = "https://open.feishu.cn/open-apis",
    ) -> None:
        if not app_id or not app_secret:
            raise FeishuAuthError("app_id and app_secret must be non-empty")

        self._app_id = app_id
        self._app_secret = app_secret
        self._base_url = base_url.rstrip("/")

        self._token: str | None = None
        self._token_expires_at: float = 0.0

        self._http = httpx.Client(timeout=30.0)

    # ----------------------------------------------------------
    # public HTTP verbs
    # ----------------------------------------------------------

    def get(
        self, path: str, params: dict[str, str] | None = None
    ) -> dict:
        """GET request with auto-auth."""
        return self._request("GET", path, params=params)

    def post(
        self, path: str, body: dict | None = None
    ) -> dict:
        """POST request with auto-auth."""
        return self._request("POST", path, json=body)

    def put(
        self, path: str, body: dict | None = None
    ) -> dict:
        """PUT request with auto-auth."""
        return self._request("PUT", path, json=body)

    def delete(self, path: str) -> dict:
        """DELETE request with auto-auth."""
        return self._request("DELETE", path)

    # ----------------------------------------------------------
    # token management
    # ----------------------------------------------------------

    def _refresh_token(self) -> str:
        """Obtain a new tenant_access_token from Feishu.

        Raises FeishuAuthError on any failure — caller must not retry.
        """
        url = f"{self._base_url}{_AUTH_PATH}"
        payload = {
            "app_id": self._app_id,
            "app_secret": self._app_secret,
        }

        try:
            resp = self._http.post(url, json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise FeishuAuthError(
                f"Token request failed: {exc}"
            ) from exc

        data = resp.json()

        if data.get("code", -1) != 0:
            raise FeishuAuthError(
                f"Token endpoint error: {data.get('msg', data)}"
            )

        token = data.get("tenant_access_token", "")
        expire = int(data.get("expire", 0))

        if not token:
            raise FeishuAuthError(
                f"No token in response: {data}"
            )

        self._token = token
        self._token_expires_at = time.time() + expire - _TOKEN_EXPIRY_BUFFER_S

        return token

    def _get_valid_token(self) -> str:
        """Return a cached token or fetch a new one."""
        if self._token and time.time() < self._token_expires_at:
            return self._token
        return self._refresh_token()

    def _clear_token(self) -> None:
        """Invalidate cached token."""
        self._token = None
        self._token_expires_at = 0.0

    # ----------------------------------------------------------
    # request execution
    # ----------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict | None = None,
    ) -> dict:
        """Execute an authenticated request with single 401-retry."""
        retried = False

        while True:
            token = self._get_valid_token()
            url = f"{self._base_url}{path}"
            headers = {"Authorization": f"Bearer {token}"}

            try:
                resp = self._http.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                )
            except httpx.HTTPError as exc:
                raise FeishuAPIError(
                    f"Transport error on {method} {path}: {exc}",
                    code=0,
                ) from exc

            # -- 401: clear token and retry once --
            if resp.status_code == 401:
                if retried:
                    raise FeishuAuthError(
                        f"Auth failed after retry: {method} {path}"
                    )
                self._clear_token()
                retried = True
                continue

            # -- other non-2xx --
            if resp.status_code >= 400:
                raise FeishuAPIError(
                    f"HTTP {resp.status_code} on {method} {path}: {resp.text[:200]}",
                    code=resp.status_code,
                )

            # -- parse JSON body --
            try:
                result = resp.json()
            except ValueError as exc:
                raise FeishuAuthError(
                    f"Invalid JSON from {path}: {resp.text[:200]}"
                ) from exc

            # -- check Feishu business-level error --
            if isinstance(result, dict) and result.get("code", 0) != 0:
                raise FeishuAuthError(
                    f"Feishu error code={result['code']}: "
                    f"{result.get('msg', result)}"
                )

            return result
