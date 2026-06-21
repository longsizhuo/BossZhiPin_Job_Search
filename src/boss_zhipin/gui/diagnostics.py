"""「复制信息去问 AI」用——把 app 上下文 + 运行日志打成一段可直接粘给任意聊天
AI 的 markdown。

背景（见产品讨论）：真实用户只下载 release（.app/.dmg），手上没有 repo / 没有
文档 / 没有 onboarding skill；去问网页版 ChatGPT/Claude 时，AI 既不认识这个小众
app、也多半不能联网抓我们的 wiki。所以这里在 app 内一键生成一段"自带上下文"的
求助文本：开头两句说清 app 是干嘛的（让 AI 对上号）+ 版本/系统/配置体检 + 文档
链接 + 最近日志。用户粘到任意 AI 就能得到针对性帮助。

**绝不抛异常**：这是求助兜底路径，任何字段取不到都降级成占位符，保证按钮永远能
出东西。语言跟随用户在 Config 选的 BOSS_LANG。

只读不写、不碰敏感值：**永远不放 API key 明文**，只说"已配置/未配置"。
"""
from __future__ import annotations

import platform

# 日志尾巴最多带这么多行——够 AI 定位问题，又不至于把剪贴板撑爆。
_MAX_LOG_LINES = 200

_DEFAULT_LANG = "zh"


def _lang() -> str:
    try:
        from boss_zhipin.gui.env_io import read_language

        lang = read_language()
        return lang if lang in ("zh", "en") else _DEFAULT_LANG
    except Exception:
        return _DEFAULT_LANG


def _safe(fn, fallback=""):
    """取值兜底：任何异常都回退，绝不让求助按钮炸掉。"""
    try:
        return fn()
    except Exception:
        return fallback


def _gather() -> dict:
    """收集一份不含敏感值的运行体检。每个字段独立兜底，取不到就降级。"""
    import os

    from boss_zhipin.gui.updates import REPO, current_version
    from boss_zhipin.gui.llm_config import read_llm_config
    from boss_zhipin.gui.resume_io import current_resume

    cfg = _safe(read_llm_config, {})
    resume = _safe(current_resume, None)

    return {
        "repo": REPO,
        "version": str(_safe(current_version, "unknown")),
        "platform": str(_safe(platform.platform, "unknown")),
        "base_url": str(cfg.get("baseUrl") or "") if isinstance(cfg, dict) else "",
        "model": str(cfg.get("model") or "") if isinstance(cfg, dict) else "",
        "has_key": bool(cfg.get("hasKey")) if isinstance(cfg, dict) else False,
        "resume": (resume or {}).get("filename", "") if isinstance(resume, dict) else "",
        "usr_name": _safe(lambda: os.environ.get("BOSS_USR_NAME", ""), ""),
    }


def build_ai_help(logs: list[str] | None = None) -> str:
    """生成可直接粘给 AI 的求助 markdown。``logs`` 是前端实时日志缓冲。"""
    lang = _lang()
    g = _gather()
    repo = g["repo"]

    log_lines = [str(x) for x in (logs or [])][-_MAX_LOG_LINES:]
    log_text = "\n".join(log_lines)

    if lang == "en":
        base_url = g["base_url"] or "(empty — OpenAI default endpoint)"
        model = g["model"] or "(not set)"
        key_state = "configured" if g["has_key"] else "missing"
        resume = g["resume"] or "(not set)"
        usr_name = g["usr_name"] or "(not set)"
        log_text = log_text or "(no logs yet — maybe Start hasn't been clicked)"
        return (
            f"I'm using an open-source desktop app, \"BOSS Zhipin Auto-Greet\" "
            f"(https://github.com/{repo}).\n"
            "What it does: it browses recommended jobs on BOSS Zhipin, pulls each job "
            "description, uses an AI to write a Chinese greeting, and sends it (a personal "
            "job-hunting helper, not a high-frequency scraper).\n"
            "I'm stuck. Based on the run info and logs below, please tell me what to do / "
            "why it's failing, with concrete steps.\n\n"
            "## Environment\n"
            f"- Version: {g['version']}\n"
            f"- OS: {g['platform']}\n\n"
            "## Current config\n"
            f"- AI endpoint: {base_url}\n"
            f"- Model: {model}\n"
            f"- API key: {key_state}\n"
            f"- Resume: {resume}\n"
            f"- Greeting signature (name): {usr_name}\n\n"
            "## Docs / FAQ\n"
            f"- Guide: https://github.com/{repo}/blob/master/README_EN.md\n"
            f"- FAQ: https://github.com/{repo}/blob/master/docs/wiki/faq.md\n"
            f"- Troubleshooting: https://github.com/{repo}/blob/master/docs/wiki/troubleshooting.md\n\n"
            "## Recent logs\n"
            "```\n"
            f"{log_text}\n"
            "```\n"
        )

    base_url = g["base_url"] or "(空 —— OpenAI 默认端点)"
    model = g["model"] or "(未填)"
    key_state = "已配置" if g["has_key"] else "未配置"
    resume = g["resume"] or "(未设置)"
    usr_name = g["usr_name"] or "(未填)"
    log_text = log_text or "(暂无日志 —— 可能还没点「开始」)"
    return (
        f"我在用一个开源桌面 App「BOSS 直聘 · 自动打招呼助手」"
        f"(https://github.com/{repo})。\n"
        "它的作用：自动在 BOSS 直聘的推荐岗位里抓职位描述，用 AI 生成中文招呼语并"
        "打招呼（个人求职辅助工具，不是高频爬虫）。\n"
        "我遇到了使用问题，请根据下面的运行信息和日志，帮我判断该怎么操作 / 为什么"
        "报错，并给出具体步骤。\n\n"
        "## 运行环境\n"
        f"- 版本：{g['version']}\n"
        f"- 系统：{g['platform']}\n\n"
        "## 当前配置\n"
        f"- AI 端点：{base_url}\n"
        f"- 模型：{model}\n"
        f"- API key：{key_state}\n"
        f"- 简历：{resume}\n"
        f"- 招呼语署名：{usr_name}\n\n"
        "## 文档 / FAQ\n"
        f"- 使用说明：https://github.com/{repo}/blob/master/README.md\n"
        f"- 常见问题：https://github.com/{repo}/blob/master/docs/wiki/faq.md\n"
        f"- 排错指南：https://github.com/{repo}/blob/master/docs/wiki/troubleshooting.md\n\n"
        "## 最近日志\n"
        "```\n"
        f"{log_text}\n"
        "```\n"
    )
