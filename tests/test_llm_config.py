"""gui.llm_config 的读/写——通用端点 (base_url + key + model) 的 .env 行为。

重点：
- 读以 **.env 文件** 为准（GUI 启动时 os.environ 还没 load）。
- 换端点不传 key **不能清掉** 已存的 key。
"""
from __future__ import annotations

import pytest

from boss_zhipin.gui import llm_config as lc


@pytest.fixture
def in_tmp_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for env in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(env, raising=False)
    return tmp_path


def test_read_empty(in_tmp_cwd):
    cfg = lc.read_llm_config()
    assert cfg["baseUrl"] == ""
    assert cfg["model"] == ""
    assert cfg["hasKey"] is False
    # 预设列表非空，且带常见平台
    names = {p["name"] for p in cfg["presets"]}
    assert {"deepseek", "openai", "claude", "qwen", "glm", "doubao"} <= names


def test_write_then_read_roundtrip(in_tmp_cwd):
    lc.write_llm_config("https://api.deepseek.com", "deepseek-chat", "sk-xxx")

    env_text = (in_tmp_cwd / ".env").read_text()
    assert "LLM_BASE_URL=https://api.deepseek.com" in env_text
    assert "LLM_MODEL=deepseek-chat" in env_text
    assert "LLM_API_KEY=sk-xxx" in env_text

    cfg = lc.read_llm_config()
    assert cfg["baseUrl"] == "https://api.deepseek.com"
    assert cfg["model"] == "deepseek-chat"
    assert cfg["hasKey"] is True


def test_switch_endpoint_without_key_keeps_key(in_tmp_cwd):
    """换 base_url/model 不传 key，不能清掉之前填好的 key。"""
    lc.write_llm_config("https://api.deepseek.com", "deepseek-chat", "sk-keep")
    # 换成自定义端点，但不传 key
    lc.write_llm_config("http://localhost:11434/v1", "llama3", None)

    env_text = (in_tmp_cwd / ".env").read_text()
    assert "LLM_API_KEY=sk-keep" in env_text  # key 仍在
    assert "LLM_BASE_URL=http://localhost:11434/v1" in env_text
    assert "LLM_MODEL=llama3" in env_text

    cfg = lc.read_llm_config()
    assert cfg["hasKey"] is True


def test_empty_base_url_deletes_it(in_tmp_cwd):
    """base_url 留空 = 用 OpenAI 默认端点（删掉那一行）。"""
    lc.write_llm_config("https://api.deepseek.com", "deepseek-chat", "sk-x")
    lc.write_llm_config("", "gpt-4o", None)

    cfg = lc.read_llm_config()
    assert cfg["baseUrl"] == ""
    assert cfg["model"] == "gpt-4o"
