"""env_io 的读/写 + os.environ 同步行为。

重点回归：GUI 配置页存 key 后必须**即时**反映到 ``os.environ``，否则
``detect_providers`` / ``llm._build_client`` 读到的还是启动时的旧值，
表现为"配置页存了 key，运行页还是 NO KEY、点开始没反应"（2026-06-08 实测）。
"""
import os

import pytest

from boss_zhipin.gui import env_io


@pytest.fixture
def in_tmp_cwd(tmp_path, monkeypatch):
    """把 cwd 切到临时目录——env_io 用相对路径 ``.env``。"""
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestWriteEnvSyncsEnviron:
    def test_write_sets_os_environ(self, in_tmp_cwd, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        env_io.write_env({"DEEPSEEK_API_KEY": "sk-test"})
        # 既落盘
        assert "DEEPSEEK_API_KEY=sk-test" in (in_tmp_cwd / ".env").read_text()
        # 也即时进 os.environ
        assert os.getenv("DEEPSEEK_API_KEY") == "sk-test"

    def test_detect_providers_sees_new_key_without_restart(self, in_tmp_cwd, monkeypatch):
        from boss_zhipin.providers import detect_providers

        for env in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(env, raising=False)
        assert detect_providers() == []
        env_io.write_env({"DEEPSEEK_API_KEY": "sk-test"})
        assert detect_providers() == ["deepseek"]

    def test_empty_value_pops_os_environ(self, in_tmp_cwd, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-old")
        env_io.write_env({"DEEPSEEK_API_KEY": ""})
        assert os.getenv("DEEPSEEK_API_KEY") is None

    def test_empty_value_pop_is_idempotent(self, in_tmp_cwd, monkeypatch):
        # 本来就没设——清空不能炸
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        env_io.write_env({"DEEPSEEK_API_KEY": ""})
        assert os.getenv("DEEPSEEK_API_KEY") is None

    def test_unknown_key_does_not_touch_environ(self, in_tmp_cwd, monkeypatch):
        monkeypatch.delenv("NOT_A_KNOWN_KEY", raising=False)
        env_io.write_env({"NOT_A_KNOWN_KEY": "x"})
        # 不在 KNOWN_KEYS → 既不落盘也不进 environ（防注入）
        assert os.getenv("NOT_A_KNOWN_KEY") is None


class TestReadEnv:
    def test_round_trip(self, in_tmp_cwd, monkeypatch):
        monkeypatch.delenv("BOSS_USR_NAME", raising=False)
        env_io.write_env({"BOSS_USR_NAME": "张三"})
        assert env_io.read_env().get("BOSS_USR_NAME") == "张三"

    def test_missing_file_returns_empty(self, in_tmp_cwd):
        assert env_io.read_env() == {}
