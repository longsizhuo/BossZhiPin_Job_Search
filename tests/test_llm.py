"""models.llm 的纯函数单测——目前盯 ``current_provider_label``。

这个标签决定 ``logs/llm_calls.jsonl`` 的 ``by_provider`` 分组；它的 docstring 自述
"曾经就这么错过一次"（成功路径写死过 deepseek），所以单独盯住 base_url→标签的映射。
成本估算按 model 名算、跟这个标签无关，所以这里只验分组语义。
"""
from __future__ import annotations

import pytest

from boss_zhipin.models import llm


@pytest.fixture(autouse=True)
def _clear_base_url(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)


class TestCurrentProviderLabel:
    def test_unset_base_url_defaults_to_openai(self, monkeypatch):
        # 没设 base_url → SDK 回退 api.openai.com → 标签 openai
        assert llm.current_provider_label() == "openai"

    def test_empty_string_base_url_defaults_to_openai(self, monkeypatch):
        # 空串 / 纯空白也当没设（strip 后 falsy）
        monkeypatch.setenv("LLM_BASE_URL", "   ")
        assert llm.current_provider_label() == "openai"

    @pytest.mark.parametrize(
        "base_url, expected",
        [
            ("https://api.deepseek.com", "deepseek"),
            ("https://api.anthropic.com/v1/", "claude"),
            ("https://api.openai.com/v1", "openai"),
            ("https://dashscope.aliyuncs.com/compatible-mode/v1", "custom"),
            ("http://localhost:11434/v1", "custom"),
        ],
    )
    def test_maps_known_and_unknown_hosts(self, monkeypatch, base_url, expected):
        monkeypatch.setenv("LLM_BASE_URL", base_url)
        assert llm.current_provider_label() == expected


class TestProviderLabel:
    def test_none_is_openai(self):
        assert llm._provider_label(None) == "openai"

    def test_case_insensitive(self):
        assert llm._provider_label("HTTPS://API.DEEPSEEK.COM") == "deepseek"

    def test_unknown_is_custom(self):
        assert llm._provider_label("https://my-proxy.example.com/v1") == "custom"
