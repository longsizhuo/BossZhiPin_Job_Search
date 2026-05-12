"""``main.py`` 里 provider / 用户输入 / 简历路径校验那几个辅助函数的单测。

这些函数在 PR #9 引入，是新用户第一次跑脚本时见到的入口逻辑。任何回归都会
直接劝退人，所以单测优先盯住。
"""
from __future__ import annotations

import pytest

import main


# ---------- detect_providers ----------

class TestDetectProviders:
    def test_no_keys_returns_empty(self, monkeypatch):
        for env in main.PROVIDER_ENV_KEYS.values():
            monkeypatch.delenv(env, raising=False)
        assert main.detect_providers() == []

    def test_single_key_returns_one(self, monkeypatch):
        for env in main.PROVIDER_ENV_KEYS.values():
            monkeypatch.delenv(env, raising=False)
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        assert main.detect_providers() == ["deepseek"]

    def test_empty_string_treated_as_unset(self, monkeypatch):
        # 设了但是空字符串 → 视为没配（因为 os.getenv 返回 "" 是 falsy）
        for env in main.PROVIDER_ENV_KEYS.values():
            monkeypatch.delenv(env, raising=False)
        monkeypatch.setenv("DEEPSEEK_API_KEY", "")
        assert main.detect_providers() == []

    def test_multiple_keys_returns_all(self, monkeypatch):
        for env in main.PROVIDER_ENV_KEYS.values():
            monkeypatch.delenv(env, raising=False)
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        result = main.detect_providers()
        # 顺序按 PROVIDER_ENV_KEYS 字典声明顺序
        assert set(result) == {"deepseek", "claude"}
        assert result == ["deepseek", "claude"]


# ---------- pick_provider ----------

class TestPickProvider:
    def test_no_keys_exits(self, monkeypatch, capsys):
        for env in main.PROVIDER_ENV_KEYS.values():
            monkeypatch.delenv(env, raising=False)
        with pytest.raises(SystemExit) as exc:
            main.pick_provider()
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "没在环境里找到任何 LLM provider 的 API key" in out
        # 必须列出 signup URL，让用户能直接申请
        assert "platform.deepseek.com" in out
        assert "platform.openai.com" in out
        assert "console.anthropic.com" in out

    def test_single_key_skips_menu(self, monkeypatch, capsys):
        for env in main.PROVIDER_ENV_KEYS.values():
            monkeypatch.delenv(env, raising=False)
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        assert main.pick_provider() == "deepseek"
        out = capsys.readouterr().out
        assert "自动选用" in out
        assert "deepseek" in out

    def test_multiple_keys_prompts_and_picks(self, monkeypatch, capsys):
        for env in main.PROVIDER_ENV_KEYS.values():
            monkeypatch.delenv(env, raising=False)
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        # 模拟用户输入 "2"（选 claude）
        monkeypatch.setattr("builtins.input", lambda _prompt="": "2")
        assert main.pick_provider() == "claude"

    def test_multiple_keys_invalid_then_valid(self, monkeypatch):
        for env in main.PROVIDER_ENV_KEYS.values():
            monkeypatch.delenv(env, raising=False)
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        inputs = iter(["", "abc", "99", "1"])
        monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
        assert main.pick_provider() == "deepseek"


# ---------- ensure_usr_name ----------

class TestEnsureUsrName:
    def test_env_var_short_circuit(self, monkeypatch):
        monkeypatch.setenv("BOSS_USR_NAME", "张三")
        assert main.ensure_usr_name() == "张三"

    def test_env_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("BOSS_USR_NAME", "  张三  ")
        assert main.ensure_usr_name() == "张三"

    def test_empty_env_falls_through_to_prompt(self, monkeypatch):
        monkeypatch.setenv("BOSS_USR_NAME", "")
        monkeypatch.setattr("builtins.input", lambda _prompt="": "李四")
        assert main.ensure_usr_name() == "李四"

    def test_empty_input_loops(self, monkeypatch):
        monkeypatch.delenv("BOSS_USR_NAME", raising=False)
        inputs = iter(["", "   ", "王五"])
        monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
        assert main.ensure_usr_name() == "王五"


# ---------- ensure_resume_path ----------

class TestEnsureResumePath:
    def test_default_path_when_unset(self, monkeypatch, tmp_path):
        # 创建默认路径的简历文件
        resume = tmp_path / "resume" / "my_cover.pdf"
        resume.parent.mkdir(parents=True)
        resume.write_bytes(b"%PDF-1.0\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("RESUME_PATH", raising=False)
        assert main.ensure_resume_path() == "resume/my_cover.pdf"

    def test_env_override_used(self, monkeypatch, tmp_path):
        custom = tmp_path / "my_resume.pdf"
        custom.write_bytes(b"%PDF-1.0\n")
        monkeypatch.setenv("RESUME_PATH", str(custom))
        assert main.ensure_resume_path() == str(custom)

    def test_missing_file_exits(self, monkeypatch, capsys):
        monkeypatch.setenv("RESUME_PATH", "/definitely/not/a/path.pdf")
        with pytest.raises(SystemExit) as exc:
            main.ensure_resume_path()
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "找不到简历文件" in out
        assert "RESUME_PATH" in out  # 提示用户怎么解决


# ---------- get_label ----------

class TestGetLabel:
    def test_returns_env_value(self, monkeypatch):
        monkeypatch.setenv("BOSS_LABEL", "后端开发（成都）")
        assert main.get_label() == "后端开发（成都）"

    def test_unset_returns_empty(self, monkeypatch):
        monkeypatch.delenv("BOSS_LABEL", raising=False)
        assert main.get_label() == ""

    def test_whitespace_stripped(self, monkeypatch):
        monkeypatch.setenv("BOSS_LABEL", "   测试岗位   ")
        assert main.get_label() == "测试岗位"
