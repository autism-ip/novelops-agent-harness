"""
test_tools — Unit tests for OpenCLIRunner and DouyinHotspotAdapter.

[INPUT]: 依赖 app.tools 的 runner、adapter、errors、schemas
[OUTPUT]: pytest 测试用例，覆盖 BDD 场景
[POS]: tests 的工具层门禁，验证子进程调用与热点归一化行为
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.tools.adapters.douyin_hotspots import (
    DouyinAdapterResult,
    DouyinHotspotAdapter,
)
from app.tools.errors import (
    OpenCLIError,
    OpenCLIExitError,
    OpenCLIOutputError,
    OpenCLITimeoutError,
)
from app.tools.runner import OpenCLIRunner, OpenCLIResult
from app.tools.schemas import DouyinHotspotRecord


# ===================================================================
# OpenCLIRunner tests
# ===================================================================


class TestOpenCLIRunner:
    """BDD: OpenCLI subprocess execution."""

    def test_successful_run_returns_parsed_json(self):
        """Scenario: Successful command execution returns parsed JSON."""
        runner = OpenCLIRunner(binary="opencli", timeout=30)
        payload = [{"rank": 1, "title": "test"}]
        mock_proc = subprocess.CompletedProcess(
            args=["opencli", "douyin", "hotspots"],
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )
        with patch("app.tools.runner.subprocess.run", return_value=mock_proc):
            result = runner.run(["douyin", "hotspots"])

        assert isinstance(result, OpenCLIResult)
        assert result.returncode == 0
        assert result.data == payload
        assert result.duration_ms >= 0

    def test_nonzero_exit_raises_exit_error(self):
        """Scenario: Non-zero exit code raises OpenCLIExitError."""
        runner = OpenCLIRunner(binary="opencli", timeout=30)
        mock_proc = subprocess.CompletedProcess(
            args=["opencli", "douyin", "hotspots"],
            returncode=1,
            stdout="",
            stderr="connection refused",
        )
        with patch("app.tools.runner.subprocess.run", return_value=mock_proc):
            with pytest.raises(OpenCLIExitError) as exc_info:
                runner.run(["douyin", "hotspots"])

        assert exc_info.value.exit_code == 1
        assert "connection refused" in str(exc_info.value)

    def test_timeout_raises_timeout_error(self):
        """Scenario: Subprocess timeout raises OpenCLITimeoutError."""
        runner = OpenCLIRunner(binary="opencli", timeout=5)
        with patch(
            "app.tools.runner.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="opencli", timeout=5),
        ):
            with pytest.raises(OpenCLITimeoutError) as exc_info:
                runner.run(["douyin", "hotspots"])

        assert exc_info.value.timeout == 5

    def test_malformed_json_raises_output_error(self):
        """Scenario: Malformed JSON on stdout raises OpenCLIOutputError."""
        runner = OpenCLIRunner(binary="opencli", timeout=30)
        mock_proc = subprocess.CompletedProcess(
            args=["opencli", "douyin", "hotspots"],
            returncode=0,
            stdout="not json",
            stderr="",
        )
        with patch("app.tools.runner.subprocess.run", return_value=mock_proc):
            with pytest.raises(OpenCLIOutputError) as exc_info:
                runner.run(["douyin", "hotspots"])

        assert "not valid JSON" in str(exc_info.value)

    def test_custom_binary_and_timeout(self):
        """Scenario: Custom binary path and timeout are used."""
        runner = OpenCLIRunner(binary="/usr/local/bin/opencli", timeout=60)
        assert runner._bin == "/usr/local/bin/opencli"
        assert runner._timeout == 60

    def test_default_config_values(self):
        """Scenario: Default config values."""
        runner = OpenCLIRunner()
        assert runner._bin == "opencli"
        assert runner._timeout == 30

    def test_binary_not_found_raises_opencli_error(self):
        """Scenario: Binary not found raises OpenCLIError."""
        runner = OpenCLIRunner(binary="nonexistent-cli", timeout=30)
        with patch(
            "app.tools.runner.subprocess.run",
            side_effect=FileNotFoundError("No such file or directory"),
        ):
            with pytest.raises(OpenCLIError, match="not found or not executable"):
                runner.run(["douyin", "hotspots"])


# ===================================================================
# DouyinHotspotAdapter tests
# ===================================================================


class TestDouyinNormalization:
    """BDD: Douyin hotspot record normalization."""

    def _make_adapter(self, runner=None, enabled=True, command=None):
        settings = SimpleNamespace(OPENCLI_ENABLED=enabled)
        return DouyinHotspotAdapter(
            runner=runner or OpenCLIRunner(),
            settings=settings,
            command=command or ["test", "hotspots"],
        )

    def test_disabled_raises_immediately(self):
        """Scenario: OpenCLI disabled raises immediately."""
        adapter = self._make_adapter(enabled=False)
        with pytest.raises(OpenCLIError, match="OpenCLI is disabled"):
            adapter.fetch()

    def test_normalize_all_fields(self):
        """Scenario: Raw record with all fields maps correctly."""
        adapter = self._make_adapter()
        raw = {
            "rank": 1,
            "title": "某明星离婚",
            "url": "https://douyin.com/hot/1",
            "hot_value": 9876543,
            "category": "娱乐",
        }
        record = adapter._normalize(raw)

        assert record is not None
        assert record.source == "douyin"
        assert record.rank == 1
        assert record.title == "某明星离婚"
        assert record.url == "https://douyin.com/hot/1"
        assert record.heat_value == 9876543
        assert record.category == "娱乐"
        assert record.hotspot_id  # non-empty UUID
        assert len(record.dedupe_hash) == 64  # sha256 hex

    def test_normalize_alternative_field_names(self):
        """Scenario: Alternative field names map correctly."""
        adapter = self._make_adapter()
        raw = {
            "position": 5,
            "word": "某事件",
            "link": "https://example.com",
            "heat": 12345,
            "label": "社会",
        }
        record = adapter._normalize(raw)

        assert record is not None
        assert record.rank == 5
        assert record.title == "某事件"
        assert record.url == "https://example.com"
        assert record.heat_value == 12345
        assert record.category == "社会"

    def test_normalize_missing_optional_fields(self):
        """Scenario: Missing optional fields use defaults."""
        adapter = self._make_adapter()
        raw = {"rank": 3, "title": "某话题"}
        record = adapter._normalize(raw)

        assert record is not None
        assert record.rank == 3
        assert record.title == "某话题"
        assert record.url == ""
        assert record.heat_value == 0
        assert record.category == ""

    def test_normalize_no_title_returns_none(self):
        """Scenario: Record without title is dropped."""
        adapter = self._make_adapter()
        raw = {"rank": 1, "heat": 100}
        record = adapter._normalize(raw)
        assert record is None

    def test_same_title_url_same_dedupe_hash(self):
        """Scenario: Duplicate title+url produces same dedupe_hash."""
        adapter = self._make_adapter()
        raw1 = {"title": "话题A", "url": "https://x.com/1"}
        raw2 = {"title": "话题A", "url": "https://x.com/1"}
        r1 = adapter._normalize(raw1)
        r2 = adapter._normalize(raw2)

        assert r1 is not None and r2 is not None
        assert r1.dedupe_hash == r2.dedupe_hash
        assert r1.hotspot_id != r2.hotspot_id  # different UUIDs

    def test_record_default_status_is_new(self):
        """Scenario: Normalized record has default status 'new'."""
        adapter = self._make_adapter()
        raw = {"title": "测试话题", "url": "https://example.com"}
        record = adapter._normalize(raw)

        assert record is not None
        assert record.status == "new"


class TestDouyinFetch:
    """BDD: Adapter fetch end-to-end."""

    def _make_mock_runner(self, data, duration_ms=100):
        return SimpleNamespace(
            run=lambda cmd: OpenCLIResult(
                stdout=json.dumps(data),
                stderr="",
                returncode=0,
                duration_ms=duration_ms,
                data=data,
            )
        )

    def test_fetch_with_3_records(self):
        """Scenario: Full fetch pipeline with mocked runner."""
        raw_records = [
            {"rank": 1, "title": "话题1", "url": "https://a.com", "hot_value": 100},
            {"rank": 2, "title": "话题2", "url": "https://b.com", "hot_value": 200},
            {"rank": 3, "title": "话题3", "url": "https://c.com", "hot_value": 300},
        ]
        runner = self._make_mock_runner(raw_records)
        settings = SimpleNamespace(OPENCLI_ENABLED=True)
        adapter = DouyinHotspotAdapter(
            runner=runner, settings=settings, command=["test", "hotspots"],
        )

        result = adapter.fetch()

        assert isinstance(result, DouyinAdapterResult)
        assert len(result.records) == 3
        assert result.raw_count == 3
        assert result.duration_ms == 100
        for record in result.records:
            assert isinstance(record, DouyinHotspotRecord)

    def test_fetch_empty_list(self):
        """Scenario: Empty records list returns empty result."""
        runner = self._make_mock_runner([])
        settings = SimpleNamespace(OPENCLI_ENABLED=True)
        adapter = DouyinHotspotAdapter(
            runner=runner, settings=settings, command=["test", "hotspots"],
        )

        result = adapter.fetch()
        assert len(result.records) == 0
        assert result.raw_count == 0

    def test_runner_error_propagates(self):
        """Scenario: Runner error propagates through adapter."""

        def failing_run(cmd):
            raise OpenCLIExitError(exit_code=1, stderr="timeout")

        runner = SimpleNamespace(run=failing_run)
        settings = SimpleNamespace(OPENCLI_ENABLED=True)
        adapter = DouyinHotspotAdapter(
            runner=runner, settings=settings, command=["test", "hotspots"],
        )

        with pytest.raises(OpenCLIExitError, match="exited with code 1"):
            adapter.fetch()

    def test_non_list_json_raises_output_error(self):
        """Scenario: Non-list JSON response raises OpenCLIOutputError."""
        dict_data = {"error": "rate limited"}
        runner = SimpleNamespace(
            run=lambda cmd: OpenCLIResult(
                stdout=json.dumps(dict_data),
                stderr="",
                returncode=0,
                duration_ms=50,
                data=dict_data,
            )
        )
        settings = SimpleNamespace(OPENCLI_ENABLED=True)
        adapter = DouyinHotspotAdapter(
            runner=runner, settings=settings, command=["test", "hotspots"],
        )

        with pytest.raises(OpenCLIOutputError, match="expected list"):
            adapter.fetch()

    def test_non_dict_items_skipped(self):
        """Scenario: Non-dict items in list are silently skipped."""
        mixed_data = [
            {"rank": 1, "title": "有效话题"},
            None,
            "invalid string",
            42,
            {"rank": 2, "title": "另一个有效话题"},
        ]
        runner = self._make_mock_runner(mixed_data)
        settings = SimpleNamespace(OPENCLI_ENABLED=True)
        adapter = DouyinHotspotAdapter(
            runner=runner, settings=settings, command=["test", "hotspots"],
        )

        result = adapter.fetch()
        assert result.raw_count == 5
        assert len(result.records) == 2
