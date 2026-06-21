"""「复制信息去问 AI」的报告生成（gui.diagnostics.build_ai_help）。

重点：报告要自带 app 介绍（让 AI 对上号）、带上日志、跟随 BOSS_LANG 语言，且
**绝不含 API key 明文**、**绝不抛异常**（求助兜底路径）。
"""
import pytest

from boss_zhipin.gui import diagnostics


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("BOSS_LANG", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)


def test_includes_app_intro_and_logs():
    report = diagnostics.build_ai_help(["[error] boom", "second line"])
    # app 介绍 + 仓库链接，让任意 AI 对上号
    assert "BOSS" in report
    assert diagnostics._gather()["repo"] in report
    # 日志被带进去
    assert "boom" in report
    assert "second line" in report


def test_never_leaks_api_key(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-super-secret-xyz")
    report = diagnostics.build_ai_help([])
    assert "sk-super-secret-xyz" not in report
    # 只说有没有配，不露明文
    assert ("已配置" in report) or ("configured" in report)


def test_follows_language(monkeypatch):
    monkeypatch.setenv("BOSS_LANG", "en")
    report = diagnostics.build_ai_help([])
    assert "Recent logs" in report
    assert "## 最近日志" not in report


def test_empty_logs_has_placeholder():
    report = diagnostics.build_ai_help([])
    # 没日志也给占位，AI 不会以为日志段坏了
    assert "暂无日志" in report


def test_none_logs_does_not_raise():
    # 前端可能传 null/不传——不能炸
    assert isinstance(diagnostics.build_ai_help(None), str)
