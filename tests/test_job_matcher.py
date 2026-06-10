"""``models/job_matcher.py`` 的单元测试。

覆盖：
- 关键词提取/匹配：词边界（短英文词不被子串误报）、中文子串、特殊符号关键词
- ``llm_match_score``：正常解析、分数钳位、三种 fail-open（缺 key / 调用失败 /
  回复解析不出分数）、telemetry 落盘
- ``should_apply``：关键词层拒绝、LLM 层通过/拒绝
"""
from __future__ import annotations

import types

import pytest

from boss_zhipin.models import job_matcher
from boss_zhipin.models.job_matcher import (
    _find_keywords,
    extract_keywords_from_text,
    keyword_match,
    llm_match_score,
    should_apply,
)

# 临时定义一个 TECH_KEYWORDS 给测试使用
TECH_KEYWORDS = [
    "Python", "Django", "Docker", "机器学习", 
    "Go", "AI", "API", "RESTful",
    ".NET", "C++", "Node.js"
]


def _fake_response(content: str):
    """构造一个最小的 chat.completions response 替身。"""
    message = types.SimpleNamespace(content=content)
    choice = types.SimpleNamespace(message=message)
    usage = types.SimpleNamespace(prompt_tokens=100, completion_tokens=20)
    return types.SimpleNamespace(choices=[choice], usage=usage)


@pytest.fixture
def telemetry_spy(monkeypatch):
    """把 record_llm_call 换成 spy，避免测试往 logs/ 写文件。"""
    calls: list[dict] = []
    monkeypatch.setattr(
        job_matcher, "record_llm_call", lambda **kwargs: calls.append(kwargs)
    )
    return calls


@pytest.fixture
def fake_client(monkeypatch):
    """绕开 _build_client 的真实 env 检查。"""
    monkeypatch.setattr(
        job_matcher, "_build_client", lambda provider: (object(), "deepseek-chat")
    )


# ---------- 关键词提取 / 匹配 ----------

class TestExtractKeywords:
    def test_happy_path(self):
        text = "精通 Python 和 Django，熟悉 Docker 容器化部署，有机器学习项目经验"
        keywords = _find_keywords(text, TECH_KEYWORDS)
        assert {"Python", "Django", "Docker", "机器学习"} <= set(keywords)

    def test_short_keywords_not_matched_as_substring(self):
        # "Go" 不该命中 Google、"AI" 不该命中 Maintained、"API" 不该命中 Rapid
        text = "Maintained legacy services at Google with rapid iteration"
        keywords = _find_keywords(text, TECH_KEYWORDS)
        assert "Go" not in keywords
        assert "AI" not in keywords
        assert "API" not in keywords

    def test_short_keywords_matched_at_word_boundary(self):
        # 中文紧贴英文关键词是 BOSS JD 的常态，必须能命中
        text = "负责AI产品研发，使用Go语言开发RESTful API服务"
        keywords = _find_keywords(text, TECH_KEYWORDS)
        assert {"AI", "Go", "API", "RESTful"} <= set(keywords)

    def test_keywords_with_special_chars(self):
        # ".NET" 要能命中 "ASP.NET"，"C++" 要能命中 "C++11"
        text = "5年 ASP.NET 开发经验，熟悉 C++11 标准和 Node.js"
        keywords = _find_keywords(text, TECH_KEYWORDS)
        assert {".NET", "C++", "Node.js"} <= set(keywords)

    def test_case_insensitive(self):
        keywords = _find_keywords("熟悉 PYTHON 和 docker", TECH_KEYWORDS)
        assert {"Python", "Docker"} <= set(keywords)


class TestKeywordMatch:
    def test_passes_at_threshold(self):
        passed, matched = keyword_match(
            "招聘 Python 后端，熟悉 Redis 优先", ["Python", "Redis", "Go"], min_match=2
        )
        assert passed
        assert set(matched) == {"Python", "Redis"}

    def test_rejects_below_threshold(self):
        passed, matched = keyword_match(
            "招聘 Java 开发", ["Python", "Redis", "Go"], min_match=2
        )
        assert not passed
        assert matched == []


# ---------- llm_match_score ----------

class TestLlmMatchScore:
    def test_parses_score_and_reason(self, monkeypatch, fake_client, telemetry_spy):
        monkeypatch.setattr(
            job_matcher, "_call_chat_completion",
            lambda client, **kwargs: _fake_response("分数: 85\n理由: 技能高度匹配"),
        )
        score, reason = llm_match_score("JD", "简历", ["Python"])
        assert score == 85
        assert reason == "技能高度匹配"
        # telemetry 记了一条成功调用
        assert len(telemetry_spy) == 1
        assert telemetry_spy[0]["ok"] is True
        assert telemetry_spy[0]["input_tokens"] == 100

    def test_parses_fullwidth_colon(self, monkeypatch, fake_client, telemetry_spy):
        # 中文 LLM（尤其 DeepSeek）常用全角冒号回复；只认 ASCII ":" 会让解析
        # 静默失败 → fail-open 恒 100 → 第二层过滤被绕过。必须两种冒号都认。
        monkeypatch.setattr(
            job_matcher, "_call_chat_completion",
            lambda client, **kwargs: _fake_response("分数：85\n理由：技能高度匹配"),
        )
        score, reason = llm_match_score("JD", "简历", ["Python"])
        assert score == 85
        assert reason == "技能高度匹配"

    def test_score_clamped_to_100(self, monkeypatch, fake_client, telemetry_spy):
        monkeypatch.setattr(
            job_matcher, "_call_chat_completion",
            lambda client, **kwargs: _fake_response("分数: 150\n理由: 超纲了"),
        )
        score, _ = llm_match_score("JD", "简历", [])
        assert score == 100

    def test_fail_open_without_api_key(self, monkeypatch):
        # conftest 已清空 env；这里再兜一层防本机 .env 经 load_dotenv 漏进来
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        score, reason = llm_match_score("JD", "简历", [])
        assert score == 100
        assert "API key" in reason

    def test_fail_open_on_api_error(self, monkeypatch, fake_client, telemetry_spy):
        def boom(client, **kwargs):
            raise ConnectionError("network down")

        monkeypatch.setattr(job_matcher, "_call_chat_completion", boom)
        score, reason = llm_match_score("JD", "简历", [])
        assert score == 100
        assert "评分失败" in reason
        # 失败也要记 telemetry
        assert telemetry_spy[0]["ok"] is False

    def test_fail_open_on_unparseable_reply(self, monkeypatch, fake_client, telemetry_spy):
        # LLM 没按 "分数: NN" 格式回复 → 必须放行，不能按 0 分静默跳过
        monkeypatch.setattr(
            job_matcher, "_call_chat_completion",
            lambda client, **kwargs: _fake_response("我觉得这个职位很适合你！"),
        )
        score, reason = llm_match_score("JD", "简历", [])
        assert score == 100
        assert "解析失败" in reason


# ---------- should_apply ----------

class TestShouldApply:
    def test_rejected_at_keyword_stage(self):
        apply, details = should_apply(
            "招聘销售经理", ["Python", "Docker"], "简历全文", min_keyword_match=2
        )
        assert not apply
        assert details["stage"] == "keyword"
        assert "score" not in details

    def test_passes_both_stages(self, monkeypatch):
        monkeypatch.setattr(
            job_matcher, "llm_match_score", lambda jd, resume, kws: (80, "匹配")
        )
        apply, details = should_apply(
            "招聘 Python 工程师，熟悉 Docker", ["Python", "Docker"], "简历全文",
            min_llm_score=70,
        )
        assert apply
        assert details["stage"] == "llm"
        assert details["score"] == 80

    def test_rejected_at_llm_stage(self, monkeypatch):
        monkeypatch.setattr(
            job_matcher, "llm_match_score", lambda jd, resume, kws: (40, "匹配度低")
        )
        apply, details = should_apply(
            "招聘 Python 工程师，熟悉 Docker", ["Python", "Docker"], "简历全文",
            min_llm_score=70,
        )
        assert not apply
        assert details["score"] == 40
