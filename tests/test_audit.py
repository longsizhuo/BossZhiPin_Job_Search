"""``audit.py`` 的单元测试。

覆盖：
- ``validate_letter``：长度边界、CJK 字符要求、黑名单拦截、组合命中
- ``log_attempt``：JSONL 落盘格式、目录自动创建、UTF-8 中文不转义
"""
from __future__ import annotations

import json

import pytest

from audit import (
    BLACKLIST,
    MAX_LEN,
    MIN_LEN,
    ValidationResult,
    log_attempt,
    validate_letter,
)


# ---------- validate_letter ----------

class TestValidateLetter:
    def test_ok_letter_passes(self):
        letter = "您好招聘负责人，我是XX学校计算机专业的应届毕业生，看到贵公司这个职位描述里提到的Python后端开发，我有三年相关经验。期待和您进一步沟通。"
        result = validate_letter(letter)
        assert result.ok
        assert result.reasons == []

    def test_too_short_rejected(self):
        result = validate_letter("您好")
        assert not result.ok
        assert any("too_short" in r for r in result.reasons)

    def test_too_long_rejected(self):
        letter = "你好" * (MAX_LEN + 1)
        result = validate_letter(letter)
        assert not result.ok
        assert any("too_long" in r for r in result.reasons)

    def test_no_chinese_rejected(self):
        # 全英文招呼语：长度过关但拒掉
        letter = "Hello recruiter, I am a backend engineer with three years of experience in Python and distributed systems. Looking forward to chatting."
        result = validate_letter(letter)
        assert not result.ok
        assert "no_chinese_characters" in result.reasons

    @pytest.mark.parametrize("blacklisted", [
        "您好招聘负责人，Error 我是后端工程师，有三年经验。期待和您进一步沟通完整描述。",
        "您好招聘负责人，As an AI 我是后端工程师，有三年经验。期待和您进一步沟通完整描述。",
        "您好招聘负责人，我是后端工程师，```python 代码块```，有三年经验。期待沟通完整描述。",
    ])
    def test_blacklist_rejected(self, blacklisted):
        result = validate_letter(blacklisted)
        assert not result.ok
        assert any(r.startswith("blacklist:") for r in result.reasons)

    def test_blacklist_constant_includes_known_strings(self):
        # 防止后人不小心删了关键拦截规则
        assert "Error" in BLACKLIST
        assert "Traceback" in BLACKLIST
        assert "As an AI" in BLACKLIST
        assert "```" in BLACKLIST

    def test_min_max_constants_have_sane_defaults(self):
        # 测试 env override 之外的默认值
        assert MIN_LEN == 30 or MIN_LEN > 0
        assert MAX_LEN >= 100
        assert MAX_LEN > MIN_LEN

    def test_validation_result_dataclass_shape(self):
        # 接口稳定性：caller 依赖 .ok 和 .reasons 两个属性
        r = ValidationResult(ok=True)
        assert r.ok is True
        assert r.reasons == []
        r2 = ValidationResult(ok=False, reasons=["x"])
        assert r2.reasons == ["x"]


# ---------- log_attempt ----------

class TestLogAttempt:
    def test_writes_jsonl_with_chinese_unescaped(self, tmp_path, monkeypatch):
        # 重定向落盘路径到临时目录
        log_path = tmp_path / "logs" / "letters.jsonl"
        monkeypatch.setattr("audit.LOG_PATH", log_path)

        validation = validate_letter("您好招聘负责人，我是XX学校的应届生，有三年Python经验。期待沟通。")
        log_attempt(
            provider="deepseek",
            model="deepseek-chat",
            job_description="Python 后端开发",
            letter="您好招聘负责人，我是XX学校的应届生，有三年Python经验。期待沟通。",
            validation=validation,
            dry_run=True,
            sent=False,
        )

        assert log_path.exists()
        line = log_path.read_text(encoding="utf-8").strip()
        record = json.loads(line)
        # JSONL 必须有 ensure_ascii=False，中文不能转义
        assert "您好" in line
        assert "\\u" not in line  # 没有 unicode 转义

        # schema 必含字段
        assert record["provider"] == "deepseek"
        assert record["model"] == "deepseek-chat"
        assert record["dry_run"] is True
        assert record["sent"] is False
        assert record["validation_ok"] is True
        assert record["validation_reasons"] == []
        assert record["letter_len"] == len(record["letter"])
        assert "ts" in record  # ISO timestamp

    def test_creates_parent_directories(self, tmp_path, monkeypatch):
        # logs/ 目录不存在时也要能写
        log_path = tmp_path / "nested" / "deep" / "letters.jsonl"
        monkeypatch.setattr("audit.LOG_PATH", log_path)
        validation = ValidationResult(ok=True)

        log_attempt(
            provider="claude",
            model="claude-sonnet-4-6",
            job_description="JD",
            letter="测试招呼语，足够长可以通过校验门槛。",
            validation=validation,
            dry_run=False,
            sent=True,
        )
        assert log_path.exists()

    def test_appends_multiple_records(self, tmp_path, monkeypatch):
        # 同一文件多次写应该追加，不是覆盖
        log_path = tmp_path / "logs" / "letters.jsonl"
        monkeypatch.setattr("audit.LOG_PATH", log_path)
        validation = ValidationResult(ok=True)

        for i in range(3):
            log_attempt(
                provider="deepseek",
                model="deepseek-chat",
                job_description=f"JD #{i}",
                letter=f"招呼语第 {i} 条，长度需要满足最低字符要求避免被拦截。",
                validation=validation,
                dry_run=True,
                sent=False,
            )
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
        for line in lines:
            json.loads(line)  # 每行都是合法 JSON
