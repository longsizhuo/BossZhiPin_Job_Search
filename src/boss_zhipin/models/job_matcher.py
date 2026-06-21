"""
职位匹配模块：两层过滤
第一层：关键词匹配（粗筛）- 从简历自动提取关键词，与 JD 对比
第二层：LLM 评分（精筛）- 让 LLM 评估简历与 JD 的匹配度 0-100
"""
from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from pypdf import PdfReader

from boss_zhipin.audit.telemetry import record_llm_call
from boss_zhipin.models.llm import _build_client, _call_chat_completion, _provider_label

load_dotenv()
log = logging.getLogger(__name__)

# 预定义的职位类型关键词库，用于从简历中识别技能和方向已移除（完全使用动态提取）

@functools.lru_cache(maxsize=None)
def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    """关键词 → 大小写不敏感的匹配 pattern。

    纯 ASCII 关键词（"Go" / "AI" / "API"...）加词边界约束，避免子串误报：
    "Go" 命中 "Google"、"AI" 命中 "Maintained"、"API" 命中 "Rapid"。
    首/尾是非字母数字的（".NET" / "C++"）只约束字母数字那一侧，
    保证 "ASP.NET"、"C++11" 仍能命中。含中文的关键词没有词边界概念，
    保留子串匹配。
    """
    escaped = re.escape(keyword)
    if keyword.isascii():
        if keyword[0].isalnum():
            escaped = r"(?<![A-Za-z0-9])" + escaped
        if keyword[-1].isalnum():
            escaped = escaped + r"(?![A-Za-z0-9])"
    return re.compile(escaped, re.IGNORECASE)


def _find_keywords(text: str, keywords: list[str]) -> list[str]:
    return [kw for kw in keywords if _keyword_pattern(kw).search(text)]


def extract_resume_text(pdf_path: str) -> str:
    """从 PDF 简历中提取全文文本。"""
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _llm_extract_keywords(resume_text: str) -> list[str]:
    """使用 LLM 从简历中提取技术关键词。"""
    try:
        client, llm_model = _build_client()
    except RuntimeError:
        log.warning("LLM_API_KEY 未设置，无法提取专属关键词")
        return []

    prompt = f"""你是一位资深的 HR 和技术专家。请从以下简历中提取出该候选人的核心技术栈、使用的工具、以及相关的业务方向。
要求：
1. 结果必须是一个纯 JSON 数组，包含字符串格式的关键词（例如：["Java", "Spring Boot", "后端开发", "MySQL"]）。
2. 不要包含任何多余的文本、解释或 Markdown 代码块标记（不要写 ```json）。
3. 关键词数量在 10 到 30 个之间，越核心的技术越靠前。

简历内容：
{resume_text[:3000]}
"""
    t0 = time.monotonic()
    try:
        response = _call_chat_completion(
            client,
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300,
        )
        content = response.choices[0].message.content or ""
        # 简单清理可能带上的 Markdown 标记
        content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        keywords = json.loads(content)
        if isinstance(keywords, list) and all(isinstance(k, str) for k in keywords):
            log.info("🎯 LLM 成功提取出专属关键词: %s", keywords)
            return keywords
        log.warning("LLM 返回的格式不是字符串数组: %s", content)
    except Exception as e:
        log.warning("LLM 提取关键词失败 (%s)，无法提取专属关键词", e)

    return []


def extract_keywords_from_text(resume_text: str) -> list[str]:
    """从简历全文中提取技术关键词（大小写不敏感），带有本地持久化缓存。"""
    text_hash = hashlib.md5(resume_text.encode('utf-8')).hexdigest()
    cache_dir = Path("vectorstores") / text_hash
    cache_file = cache_dir / "keywords.json"

    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_keywords = json.load(f)
                if isinstance(cached_keywords, list):
                    log.info("✅ 已从本地缓存读取专属简历关键词（%d个）", len(cached_keywords))
                    return cached_keywords
        except Exception as e:
            log.warning("读取缓存关键词失败: %s", e)

    keywords = _llm_extract_keywords(resume_text)
    
    # 存入缓存
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(keywords, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning("保存缓存关键词失败: %s", e)

    return keywords


def extract_keywords_from_resume(pdf_path: str) -> list[str]:
    """从简历 PDF 中自动提取关键词，大小写不敏感。"""
    return extract_keywords_from_text(extract_resume_text(pdf_path))


def keyword_match(
    job_description: str,
    resume_keywords: list[str],
    min_match: int = 2,
) -> tuple[bool, list[str]]:
    """第一层：关键词粗筛。JD 中至少命中 min_match 个简历关键词才通过。"""
    matched = _find_keywords(job_description, resume_keywords)
    return len(matched) >= min_match, matched


def llm_match_score(
    job_description: str,
    resume_text: str,
    matched_keywords: list[str],
) -> tuple[int, str]:
    """第二层：LLM 精筛。评估简历与职位的匹配度，返回 0-100 分。

    评分链路任何一环不可用（缺 API key / 调用失败 / 回复解析不出分数）
    都 fail-open 返回 100 放行——宁可少过滤，不能因为评分挂了把职位静默跳过。
    """
    try:
        client, llm_model = _build_client()
    except RuntimeError:
        log.warning("LLM_API_KEY 未设置，跳过 LLM 评分")
        return 100, "无法评分（缺少 API key）"
    prov = _provider_label(os.getenv("LLM_BASE_URL", "").strip() or None)

    prompt = f"""你是一位专业的招聘匹配分析师。请评估以下简历与职位描述的匹配程度。

## 职位描述
{job_description}

## 简历内容
{resume_text[:2000]}

## 已匹配的关键词
{', '.join(matched_keywords)}

## 要求
请严格按以下格式回复，不要包含任何其他内容：
分数: [0-100的整数]
理由: [一句话说明，不超过50字]

评分标准：
- 90-100: 技能和经验高度匹配，非常适合
- 70-89: 大部分技能匹配，值得投递
- 50-69: 部分匹配，可以尝试
- 0-49: 匹配度低，不建议投递"""

    # _call_chat_completion 自带指数退避重试；评分调用跟招呼语生成一样
    # 记 telemetry，不然每个职位多出来的这次调用成本不进 llm_calls.jsonl
    t0 = time.monotonic()
    try:
        response = _call_chat_completion(
            client,
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )
    except Exception as e:
        record_llm_call(
            provider=prov, model=llm_model,
            input_tokens=0, output_tokens=0,
            latency_ms=int((time.monotonic() - t0) * 1000),
            ok=False, error=f"{type(e).__name__}: {e}",
        )
        log.warning("LLM 评分调用失败: %s", e)
        return 100, f"评分失败（{e}）"

    content = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    record_llm_call(
        provider="deepseek", model=llm_model,
        input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
        output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        latency_ms=int((time.monotonic() - t0) * 1000),
        ok=True,
    )

    # 冒号同时容忍 ASCII ":" 和全角 "："——中文 LLM（尤其 DeepSeek）即便 prompt
    # 给的是 ASCII 冒号，回复也常用全角。只认 ASCII 会让解析静默失败 → fail-open
    # 恒返 100 → 第二层 LLM 过滤被悄悄绕过。
    score_match = re.search(r"分数[:：]\s*(\d+)", content)
    if not score_match:
        # LLM 没按格式回复时同样 fail-open；fail-closed（按 0 分算）
        # 会把职位静默跳过，且日志里看不出原因
        log.warning("LLM 评分回复解析失败，按 100 放行。回复内容: %r", content[:200])
        return 100, "评分解析失败"

    score = min(100, max(0, int(score_match.group(1))))
    reason_match = re.search(r"理由[:：]\s*(.+)", content)
    reason = reason_match.group(1).strip() if reason_match else ""
    return score, reason


def should_apply(
    job_description: str,
    resume_keywords: list[str],
    resume_text: str,
    min_keyword_match: int = 2,
    min_llm_score: int = 70,
    exclude_keywords: list[str] | None = None,
    vectorstore=None,
) -> tuple[bool, dict]:
    """多层过滤：黑名单 -> 关键词粗筛 -> 向量语义粗筛 -> LLM 精筛。"""
    
    if exclude_keywords:
        for ex_kw in exclude_keywords:
            if _keyword_pattern(ex_kw).search(job_description):
                return False, {
                    "stage": "blacklist",
                    "reason": f"命中黑名单关键词: {ex_kw}",
                }

    if resume_keywords:
        keyword_passed, matched_keywords = keyword_match(
            job_description, resume_keywords, min_keyword_match
        )

        if not keyword_passed:
            return False, {
                "stage": "keyword",
                "matched_keywords": matched_keywords,
                "reason": f"关键词匹配不足（命中 {len(matched_keywords)}/{min_keyword_match}）",
            }
    else:
        matched_keywords = []

    if vectorstore is not None:
        is_relevant, distance = vectorstore.check_relevance(job_description)
        if not is_relevant:
            return False, {
                "stage": "vector_search",
                "reason": f"语义匹配度过低 (距离 {distance:.2f} > 阈值)",
            }
        else:
            log.debug("语义距离验证通过 (距离: %.2f)", distance)

    score, reason = llm_match_score(job_description, resume_text, matched_keywords)

    return score >= min_llm_score, {
        "stage": "llm",
        "matched_keywords": matched_keywords,
        "score": score,
        "reason": reason,
        "threshold": min_llm_score,
    }
