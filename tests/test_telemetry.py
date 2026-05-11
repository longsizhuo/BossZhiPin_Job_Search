"""``audit/telemetry.py`` 的单测。

覆盖：成本估算、JSONL 落盘格式、聚合 summary、损坏行容错。
"""
from __future__ import annotations

import json

import pytest

from audit import telemetry as tm


# ---------- estimate_cost_cny ----------

class TestEstimateCost:
    def test_known_model_returns_positive(self):
        cost = tm.estimate_cost_cny("deepseek-chat", 1_000_000, 1_000_000)
        # 1M input + 1M output = 1.0 + 2.0 = 3.0 CNY
        assert cost == pytest.approx(3.0)

    def test_unknown_model_returns_zero(self):
        # 未登记的 model 不瞎估，宁可 0
        assert tm.estimate_cost_cny("nonexistent-model", 1000, 1000) == 0.0

    def test_zero_tokens_returns_zero(self):
        assert tm.estimate_cost_cny("deepseek-chat", 0, 0) == 0.0

    def test_proportional_to_tokens(self):
        small = tm.estimate_cost_cny("deepseek-chat", 1000, 1000)
        big = tm.estimate_cost_cny("deepseek-chat", 100_000, 100_000)
        assert big == pytest.approx(small * 100)


# ---------- record_llm_call ----------

class TestRecordLlmCall:
    def test_writes_jsonl_record(self, tmp_path, monkeypatch):
        path = tmp_path / "logs" / "llm_calls.jsonl"
        monkeypatch.setattr(tm, "TELEMETRY_PATH", path)

        record = tm.record_llm_call(
            provider="deepseek",
            model="deepseek-chat",
            input_tokens=1000,
            output_tokens=500,
            latency_ms=1234,
            letter_len=180,
            ok=True,
            error=None,
        )
        assert path.exists()
        line = path.read_text(encoding="utf-8").strip()
        on_disk = json.loads(line)
        assert on_disk["provider"] == "deepseek"
        assert on_disk["total_tokens"] == 1500
        assert on_disk["cost_cny"] == pytest.approx(0.002)  # 0.001 + 0.001
        assert record == on_disk

    def test_failed_call_recorded_with_error(self, tmp_path, monkeypatch):
        path = tmp_path / "logs" / "llm_calls.jsonl"
        monkeypatch.setattr(tm, "TELEMETRY_PATH", path)

        record = tm.record_llm_call(
            provider="openai",
            model="gpt-4o",
            input_tokens=0,
            output_tokens=0,
            latency_ms=200,
            ok=False,
            error="rate_limit",
        )
        assert record["ok"] is False
        assert record["error"] == "rate_limit"
        assert record["total_tokens"] == 0
        assert record["cost_cny"] == 0.0

    def test_disk_failure_does_not_raise(self, monkeypatch):
        # 模拟落盘抛异常（路径权限错），caller 应该照常拿到 record
        monkeypatch.setattr(
            tm, "TELEMETRY_PATH",
            tm.Path("/proc/0/forbidden/llm_calls.jsonl"),
        )
        record = tm.record_llm_call(
            provider="deepseek", model="deepseek-chat",
            input_tokens=100, output_tokens=50, latency_ms=300,
        )
        assert record["provider"] == "deepseek"  # 业务路径不该被打断


# ---------- read_telemetry / telemetry_summary ----------

class TestRead:
    def test_returns_empty_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(tm, "TELEMETRY_PATH", tmp_path / "absent.jsonl")
        assert tm.read_telemetry() == []
        assert tm.telemetry_summary() == {
            "total_calls": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost_cny": 0.0,
            "by_provider": {},
        }

    def test_corrupt_line_skipped(self, tmp_path, monkeypatch):
        path = tmp_path / "llm.jsonl"
        path.write_text(
            '{"provider":"deepseek","model":"deepseek-chat","input_tokens":100,"output_tokens":50,"total_tokens":150,"latency_ms":200,"cost_cny":0.0002,"letter_len":80,"ok":true}\n'
            "this is not json\n"
            '{"provider":"openai","model":"gpt-4o","input_tokens":200,"output_tokens":100,"total_tokens":300,"latency_ms":1000,"cost_cny":0.01,"letter_len":120,"ok":true}\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(tm, "TELEMETRY_PATH", path)
        records = tm.read_telemetry()
        assert len(records) == 2
        assert records[0]["provider"] == "deepseek"
        assert records[1]["provider"] == "openai"

    def test_summary_aggregates_by_provider(self, tmp_path, monkeypatch):
        path = tmp_path / "llm.jsonl"
        monkeypatch.setattr(tm, "TELEMETRY_PATH", path)
        for _ in range(3):
            tm.record_llm_call(
                provider="deepseek", model="deepseek-chat",
                input_tokens=1000, output_tokens=500, latency_ms=200,
            )
        tm.record_llm_call(
            provider="claude", model="claude-sonnet-4-6",
            input_tokens=2000, output_tokens=1000, latency_ms=1500,
        )

        s = tm.telemetry_summary()
        assert s["total_calls"] == 4
        assert s["total_input_tokens"] == 1000 * 3 + 2000
        assert s["by_provider"]["deepseek"]["calls"] == 3
        assert s["by_provider"]["claude"]["calls"] == 1
        assert s["by_provider"]["deepseek"]["avg_latency_ms"] == 200
        # cost 累加 > 0
        assert s["by_provider"]["deepseek"]["cost_cny"] > 0
        assert s["by_provider"]["claude"]["cost_cny"] > 0
        # 不应该泄漏内部累加键
        assert "_lat_sum" not in s["by_provider"]["deepseek"]

    def test_since_limit_honored(self, tmp_path, monkeypatch):
        path = tmp_path / "llm.jsonl"
        monkeypatch.setattr(tm, "TELEMETRY_PATH", path)
        for i in range(10):
            tm.record_llm_call(
                provider="deepseek", model="deepseek-chat",
                input_tokens=i, output_tokens=i, latency_ms=100,
            )
        recent = tm.read_telemetry(since=3)
        assert len(recent) == 3
        # 取的是末尾 3 条
        assert recent[-1]["input_tokens"] == 9
