"""
runner — OpenCLIRunner subprocess execution.

[INPUT]: 依赖 app.tools.errors 的 OpenCLITimeoutError / OpenCLIExitError / OpenCLIOutputError
[OUTPUT]: OpenCLIRunner class, OpenCLIResult frozen dataclass
[POS]: tools 包的执行层，被 adapter 消费，隔离子进程调用
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

from app.tools.errors import OpenCLIExitError, OpenCLIOutputError, OpenCLITimeoutError


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OpenCLIResult:
    """Result of a successful OpenCLI subprocess invocation.

    ``data`` holds the parsed JSON payload (list | dict | None).
    When the runner parses stdout as JSON, the decoded object is stored here
    so adapters can consume it without re-parsing.
    """

    stdout: str
    stderr: str
    returncode: int
    duration_ms: int
    data: Any = field(default=None, hash=False)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class OpenCLIRunner:
    """Tool-agnostic subprocess runner for OpenCLI commands.

    Captures stdout/stderr, enforces timeout, validates JSON output,
    and raises typed exceptions on failure.
    """

    def __init__(self, binary: str = "opencli", timeout: int = 30) -> None:
        self._bin = binary
        self._timeout = timeout

    def run(self, command: list[str], timeout: int | None = None) -> OpenCLIResult:
        """Execute an OpenCLI command and return the parsed result.

        Args:
            command: Arguments to pass after the binary name.
            timeout: Override the default timeout in seconds.

        Returns:
            OpenCLIResult with stdout, stderr, returncode, duration_ms.

        Raises:
            OpenCLITimeoutError: Subprocess exceeded timeout.
            OpenCLIExitError: Subprocess exited non-zero.
            OpenCLIOutputError: stdout was not valid JSON.
        """
        effective_timeout = timeout if timeout is not None else self._timeout
        cmd = [self._bin, *command]

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise OpenCLITimeoutError(
                timeout=effective_timeout,
                cause=exc,
            ) from exc

        duration_ms = int((time.monotonic() - start) * 1000)

        if proc.returncode != 0:
            raise OpenCLIExitError(
                exit_code=proc.returncode,
                stderr=proc.stderr.strip(),
            )

        # Validate JSON — all OpenCLI output is expected to be JSON
        try:
            parsed = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise OpenCLIOutputError(
                message=f"OpenCLI output is not valid JSON: {exc}",
                cause=exc,
            ) from exc

        return OpenCLIResult(
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
            duration_ms=duration_ms,
            data=parsed,
        )
