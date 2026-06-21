"""``main.py`` 里 provider / 用户输入 / 简历路径校验那几个辅助函数的单测。

这些函数在 PR #9 引入，是新用户第一次跑脚本时见到的入口逻辑。任何回归都会
直接劝退人，所以单测优先盯住。
"""
from __future__ import annotations

import pytest

from boss_zhipin import cli as main  # test 内继续叫 main，少改


# ---------- ensure_llm_configured ----------
# 重构后（2026-06）不再分 provider：统一一个 OpenAI 兼容端点（LLM_BASE_URL +
# LLM_API_KEY + LLM_MODEL），CLI 只校验 LLM_API_KEY 配了没。

class TestEnsureLlmConfigured:
    def test_no_key_exits_with_signup_help(self, monkeypatch, capsys):
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        with pytest.raises(SystemExit) as exc:
            main.ensure_llm_configured()
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "LLM_API_KEY" in out
        # 列出常见平台申请地址，让用户能直接申请
        assert "platform.deepseek.com" in out

    def test_empty_string_treated_as_unset(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "")
        with pytest.raises(SystemExit):
            main.ensure_llm_configured()

    def test_key_set_returns_without_exit(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "sk-test")
        assert main.ensure_llm_configured() is None
        assert main.is_llm_configured() is True


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
