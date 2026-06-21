"""gui.provider_config 的读/写——服务商选择器的 .env 真相源行为。

重点：
- 读以 **.env 文件** 为准（GUI 启动时 os.environ 还没 load）。
- 切服务商不传 key **不能清掉** 已存的 key（区别于 env_io 的"空=删除"）。
"""
from __future__ import annotations

import pytest

from boss_zhipin.gui import provider_config as pc


@pytest.fixture
def in_tmp_cwd(tmp_path, monkeypatch):
    """切到临时 cwd——provider_config / env_io 都用相对路径 ``.env``。

    同时清掉会被 write_env 写进 os.environ 的几个 key，让 monkeypatch 在
    teardown 时还原，不污染其他用例。
    """
    monkeypatch.chdir(tmp_path)
    for env in ("BOSS_PROVIDER", "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    return tmp_path


def test_read_empty_defaults_to_deepseek(in_tmp_cwd):
    cfg = pc.read_provider_config()
    assert cfg["active"] == "deepseek"
    # 三家都列出，但都没配 key
    names = [p["name"] for p in cfg["providers"]]
    assert names == ["deepseek", "chatgpt", "claude"]
    assert all(p["hasKey"] is False for p in cfg["providers"])
    # 显示名给的是品牌名，不是内部代号
    labels = {p["name"]: p["label"] for p in cfg["providers"]}
    assert labels["chatgpt"] == "OpenAI"


def test_write_then_read_roundtrip(in_tmp_cwd):
    pc.write_provider_config("claude", "sk-ant-xxx")

    # 落盘了 BOSS_PROVIDER + 对应 key
    env_text = (in_tmp_cwd / ".env").read_text()
    assert "BOSS_PROVIDER=claude" in env_text
    assert "ANTHROPIC_API_KEY=sk-ant-xxx" in env_text

    cfg = pc.read_provider_config()
    assert cfg["active"] == "claude"
    claude = next(p for p in cfg["providers"] if p["name"] == "claude")
    assert claude["hasKey"] is True


def test_active_falls_back_to_first_configured(in_tmp_cwd):
    """没存过 BOSS_PROVIDER 时，active 落到第一个已配 key 的服务商。"""
    # 只配 OpenAI 的 key，不写 BOSS_PROVIDER
    from boss_zhipin.gui.env_io import write_env
    write_env({"OPENAI_API_KEY": "sk-openai"})

    cfg = pc.read_provider_config()
    assert cfg["active"] == "chatgpt"


def test_switch_provider_without_key_keeps_existing_key(in_tmp_cwd):
    """切服务商不传 key，不能误删之前填好的 key。"""
    pc.write_provider_config("claude", "sk-ant-keep")
    # 切到 deepseek，但 deepseek 还没 key，且不传 api_key
    pc.write_provider_config("deepseek", None)

    env_text = (in_tmp_cwd / ".env").read_text()
    assert "ANTHROPIC_API_KEY=sk-ant-keep" in env_text  # 旧 key 仍在
    assert "BOSS_PROVIDER=deepseek" in env_text

    cfg = pc.read_provider_config()
    assert cfg["active"] == "deepseek"
    claude = next(p for p in cfg["providers"] if p["name"] == "claude")
    assert claude["hasKey"] is True  # claude 的 key 没被清


def test_unknown_provider_raises(in_tmp_cwd):
    with pytest.raises(ValueError):
        pc.write_provider_config("gemini", "sk-x")
