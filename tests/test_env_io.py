"""env_io 的读/写 + os.environ 同步行为。

重点回归：GUI 配置页存 key 后必须**即时**反映到 ``os.environ``，否则
``llm._build_client`` 读到的还是启动时的旧值，表现为"配置页存了 key，运行页
还是 NO KEY、点开始没反应"（2026-06-08 实测）。LLM 端点 key 现在叫
``LLM_API_KEY``（重构后统一一个 OpenAI 兼容端点）。
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
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        env_io.write_env({"LLM_API_KEY": "sk-test"})
        # 既落盘
        assert "LLM_API_KEY=sk-test" in (in_tmp_cwd / ".env").read_text()
        # 也即时进 os.environ
        assert os.getenv("LLM_API_KEY") == "sk-test"

    def test_is_configured_sees_new_key_without_restart(self, in_tmp_cwd, monkeypatch):
        from boss_zhipin.providers import is_llm_configured

        monkeypatch.delenv("LLM_API_KEY", raising=False)
        assert is_llm_configured() is False
        env_io.write_env({"LLM_API_KEY": "sk-test"})
        assert is_llm_configured() is True

    def test_empty_value_pops_os_environ(self, in_tmp_cwd, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "sk-old")
        env_io.write_env({"LLM_API_KEY": ""})
        assert os.getenv("LLM_API_KEY") is None

    def test_empty_value_pop_is_idempotent(self, in_tmp_cwd, monkeypatch):
        # 本来就没设——清空不能炸
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        env_io.write_env({"LLM_API_KEY": ""})
        assert os.getenv("LLM_API_KEY") is None

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


class TestLanguage:
    def test_round_trip(self, in_tmp_cwd, monkeypatch):
        monkeypatch.delenv(env_io.LANG_ENV, raising=False)
        env_io.write_language("en")
        # 既落盘也即时进 os.environ（无需重启 App）
        assert f"{env_io.LANG_ENV}=en" in (in_tmp_cwd / ".env").read_text()
        assert os.getenv(env_io.LANG_ENV) == "en"
        assert env_io.read_language() == "en"

    def test_unset_returns_empty(self, in_tmp_cwd, monkeypatch):
        # 没设过 → 空字符串，前端据此回退到系统探测的默认
        monkeypatch.delenv(env_io.LANG_ENV, raising=False)
        assert env_io.read_language() == ""

    def test_reads_from_file_when_not_in_environ(self, in_tmp_cwd, monkeypatch):
        # 写完把 environ 抹掉，模拟 GUI 早期 env 还没 load——应回退读 .env 文件
        env_io.write_language("zh")
        monkeypatch.delenv(env_io.LANG_ENV, raising=False)
        assert env_io.read_language() == "zh"


class TestLetterPrompt:
    def test_round_trip(self, in_tmp_cwd, monkeypatch):
        monkeypatch.delenv(env_io.LETTER_PROMPT_ENV, raising=False)
        env_io.write_letter_prompt("自定义：署名 {usr_name}")
        assert os.getenv(env_io.LETTER_PROMPT_ENV) == "自定义：署名 {usr_name}"
        got = env_io.read_letter_prompt()
        assert got["prompt"] == "自定义：署名 {usr_name}"
        assert got["default"]  # 默认全文非空

    def test_unset_returns_empty_with_default(self, in_tmp_cwd, monkeypatch):
        monkeypatch.delenv(env_io.LETTER_PROMPT_ENV, raising=False)
        got = env_io.read_letter_prompt()
        assert got["prompt"] == ""
        assert "真人" in got["default"]  # 内置默认是"像真人"那版

    def test_empty_write_clears(self, in_tmp_cwd, monkeypatch):
        env_io.write_letter_prompt("x")
        env_io.write_letter_prompt("")
        assert os.getenv(env_io.LETTER_PROMPT_ENV) is None
