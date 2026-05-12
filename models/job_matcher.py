"""
职位匹配模块：两层过滤
第一层：关键词匹配（粗筛）- 从简历自动提取关键词，与 JD 对比
第二层：LLM 评分（精筛）- 让 LLM 评估简历与 JD 的匹配度 0-100
"""
from __future__ import annotations

import logging
import os
import re

from dotenv import load_dotenv
from pypdf import PdfReader

load_dotenv()
log = logging.getLogger(__name__)

# 预定义的职位类型关键词库，用于从简历中识别技能和方向
TECH_KEYWORDS = [
    # 开发方向
    "后端开发", "前端开发", "全栈开发", "移动开发", "客户端开发",
    "iOS开发", "Android开发", "嵌入式开发", "游戏开发", "小程序开发",
    # 技术栈
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Golang",
    "C++", "C#", "Rust", "PHP", "Ruby", "Swift", "Kotlin", "Scala",
    "React", "Vue", "Angular", "Node.js", "Django", "Flask", "FastAPI",
    "Spring", "SpringBoot", "Spring Boot", "MyBatis", "Hibernate",
    ".NET", "Flutter", "React Native", "UniApp",
    # 数据与AI
    "数据分析", "数据开发", "数据挖掘", "数据仓库", "大数据",
    "机器学习", "深度学习", "自然语言处理", "NLP", "计算机视觉", "CV",
    "人工智能", "AI", "LLM", "大模型", "AIGC", "RAG",
    "数据库", "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
    "Hadoop", "Spark", "Flink", "Kafka", "Hive",
    # 运维与云
    "运维", "DevOps", "SRE", "云计算", "云原生",
    "Docker", "Kubernetes", "K8s", "AWS", "Azure", "GCP", "阿里云", "腾讯云",
    "Linux", "CI/CD", "Jenkins", "Terraform",
    # 测试
    "测试", "自动化测试", "性能测试", "测试开发", "QA",
    "Selenium", "Pytest", "JUnit",
    # 产品与设计
    "产品经理", "项目管理", "UI设计", "UX设计", "交互设计",
    # 安全
    "网络安全", "信息安全", "安全开发", "渗透测试",
    # 通用技能
    "微服务", "分布式", "高并发", "高可用", "消息队列",
    "RESTful", "API", "GraphQL", "gRPC", "WebSocket",
    "Git", "Agile", "Scrum",
]


def extract_resume_text(pdf_path: str) -> str:
    """从 PDF 简历中提取全文文本。"""
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_keywords_from_resume(pdf_path: str) -> list[str]:
    """从简历 PDF 中自动提取关键词，大小写不敏感。"""
    resume_text = extract_resume_text(pdf_path)
    resume_upper = resume_text.upper()
    return [kw for kw in TECH_KEYWORDS if kw.upper() in resume_upper]


def keyword_match(
    job_description: str,
    resume_keywords: list[str],
    min_match: int = 2,
) -> tuple[bool, list[str]]:
    """第一层：关键词粗筛。JD 中至少命中 min_match 个简历关键词才通过。"""
    jd_upper = job_description.upper()
    matched = [kw for kw in resume_keywords if kw.upper() in jd_upper]
    return len(matched) >= min_match, matched


def llm_match_score(
    job_description: str,
    resume_text: str,
    matched_keywords: list[str],
) -> tuple[int, str]:
    """第二层：LLM 精筛。评估简历与职位的匹配度，返回 0-100 分。"""
    from openai import OpenAI

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        log.warning("DEEPSEEK_API_KEY 未设置，跳过 LLM 评分")
        return 100, "无法评分（缺少 API key）"

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

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

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )
        content = response.choices[0].message.content or ""
    except Exception as e:
        log.warning("LLM 评分调用失败: %s", e)
        return 100, f"评分失败（{e}）"

    score = 0
    reason = ""
    score_match = re.search(r"分数:\s*(\d+)", content)
    reason_match = re.search(r"理由:\s*(.+)", content)
    if score_match:
        score = min(100, max(0, int(score_match.group(1))))
    if reason_match:
        reason = reason_match.group(1).strip()

    return score, reason


def should_apply(
    job_description: str,
    resume_keywords: list[str],
    resume_text: str,
    min_keyword_match: int = 2,
    min_llm_score: int = 70,
) -> tuple[bool, dict]:
    """两层过滤：先关键词粗筛，再 LLM 精筛。"""
    keyword_passed, matched_keywords = keyword_match(
        job_description, resume_keywords, min_keyword_match
    )

    if not keyword_passed:
        return False, {
            "stage": "keyword",
            "matched_keywords": matched_keywords,
            "reason": f"关键词匹配不足（命中 {len(matched_keywords)}/{min_keyword_match}）",
        }

    score, reason = llm_match_score(job_description, resume_text, matched_keywords)

    return score >= min_llm_score, {
        "stage": "llm",
        "matched_keywords": matched_keywords,
        "score": score,
        "reason": reason,
        "threshold": min_llm_score,
    }
