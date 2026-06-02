"""
errors — OpenCLI error hierarchy.

[INPUT]: 无外部依赖，纯异常定义
[OUTPUT]: OpenCLIError, OpenCLITimeoutError, OpenCLIExitError, OpenCLIOutputError
[POS]: tools 包的错误契约层，被 runner 和 adapter 消费
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""


class OpenCLIError(Exception):
    """Base exception for all OpenCLI tool failures."""

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class OpenCLITimeoutError(OpenCLIError):
    """Subprocess exceeded the configured timeout."""

    def __init__(self, timeout: int, *, cause: BaseException | None = None) -> None:
        super().__init__(f"OpenCLI timed out after {timeout}s", cause=cause)
        self.timeout = timeout


class OpenCLIExitError(OpenCLIError):
    """Subprocess exited with a non-zero return code."""

    def __init__(
        self,
        exit_code: int,
        stderr: str,
        *,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(
            f"OpenCLI exited with code {exit_code}: {stderr[:200]}",
            cause=cause,
        )
        self.exit_code = exit_code
        self.stderr = stderr


class OpenCLIOutputError(OpenCLIError):
    """Subprocess output was malformed JSON or missing required fields."""

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message, cause=cause)
