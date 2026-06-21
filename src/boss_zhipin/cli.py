"""CLI 入口。

启动流程：
1. 读 ``.env``，校验 ``LLM_API_KEY`` 配好了没（端点 / model 由 ``LLM_*`` 决定）。
2. 兜底 ``BOSS_USR_NAME`` / ``BOSS_LABEL`` / ``RESUME_PATH`` 三个可选配置：
   不设就 prompt 用户输入或用默认值。
3. 进入主循环——统一走一个 OpenAI 兼容端点，不再分 provider 分支。

跑法：``uv run main.py`` / ``uv run python -m boss_zhipin`` / ``boss-zhipin``（pyproject script）
三种等价。

设计：用户输入提示用 ``print``，业务流程用 ``logging``。logging 在
``_cli_main`` 里 ``basicConfig`` 统一初始化——**不在 module top**，避免
``import boss_zhipin.cli`` 时改掉 GUI 进程的 logging 配置。

注意：本模块自己不在 import-time 调 ``load_dotenv``，但顶层 import 的
``models.*`` 子模块会（历史行为）。所以 ``import boss_zhipin.cli`` 仍会把
``.env`` 读进 ``os.environ``——GUI 的 ``detect_providers`` 依赖这一点，
不要为了"纯净 import"把这些 import 延迟掉。
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import nodriver as uc
from dotenv import load_dotenv

from boss_zhipin.models.job_matcher import extract_keywords_from_text, extract_resume_text
# LLM_PRESETS / is_llm_configured 住在轻量的 boss_zhipin.providers，
# 让 PyTauri 的 Config 命令不被 cli.py 的重 import 链拖累
# （cli 的 vectorization import 会触发 sentence_transformers → torch，3-10s）。
from boss_zhipin.providers import (
    LLM_PRESETS,
    is_llm_configured,
)
from boss_zhipin.vectorization import embed_resume
from boss_zhipin.website_oper.write_response import send_job_descriptions_to_chat

log = logging.getLogger(__name__)

# BOSS 推荐 feed 入口。CLI 和 GUI 都从这里进。
RECOMMEND_URL = "https://www.zhipin.com/web/geek/job-recommend?ka=header-job-recommend"

# 简历默认路径。CLI（ensure_resume_path）和 GUI（tauri 的 factory）共用。
DEFAULT_RESUME_PATH = "resume/my_cover.pdf"

__all__ = [
    "LLM_PRESETS",
    "is_llm_configured",
    "RECOMMEND_URL",
    "DEFAULT_RESUME_PATH",
    "ensure_llm_configured",
    "ensure_usr_name",
    "ensure_resume_path",
    "run_provider",
]


def ensure_llm_configured() -> None:
    """没填 LLM_API_KEY 就打印各家申请地址并退出。

    端点 / model 统一由 ``LLM_*`` 决定（GUI 选预设会自动填），CLI 这里只兜底
    检查 key 在不在；真正构造 client 在 ``llm._build_client``（会校验 LLM_MODEL）。
    """
    if is_llm_configured():
        return
    print("❌ 没设置 LLM_API_KEY。")
    print("   选一家申请 key，填进 .env 的 LLM_API_KEY（.env.example 有样板）：")
    for preset in LLM_PRESETS.values():
        print(f"     • {preset['label']:<18} {preset['signup_url']}")
        print(f"       LLM_BASE_URL={preset['base_url']}  LLM_MODEL={preset['model']}")
    sys.exit(1)


def ensure_usr_name() -> str:
    name = os.getenv("BOSS_USR_NAME", "").strip()
    if name:
        return name
    while True:
        name = input("请输入你的名字（用于打招呼语结尾的署名）: ").strip()
        if name:
            return name
        print("不能为空")


def ensure_resume_path() -> str:
    resume_path = os.getenv("RESUME_PATH", "").strip() or DEFAULT_RESUME_PATH
    if not Path(resume_path).is_file():
        print(f"❌ 找不到简历文件：{resume_path}")
        print(f"   请把 PDF 简历放到这个路径，或者在 .env 设 RESUME_PATH 指向其他位置。")
        sys.exit(1)
    return resume_path


def get_label() -> str:
    """求职 tag 是可选的——为空就让 BOSS 给默认推荐 feed。"""
    return os.getenv("BOSS_LABEL", "").strip()


async def run_provider(
    usr_name: str,
    label: str,
    dry_run: bool,
    resume_path: str,
) -> None:
    """简历预处理 + 主循环，CLI 和 GUI 共用的唯一入口。

    用哪个 LLM 端点 / model 由 ``LLM_*`` 环境变量决定（见 ``llm._build_client``），
    不再按 provider 分支——三家都是 OpenAI 兼容端点，走同一条 RAG + chat
    completions 通路。

    必须在同一个事件循环里 await（nodriver CDP 跨 run_until_complete 会半死，
    见 ``_cli_main`` 的注释）。
    """
    # 从简历自动提取关键词和全文（用于职位匹配过滤）
    resume_text = extract_resume_text(resume_path)
    resume_keywords = extract_keywords_from_text(resume_text)
    log.info("📋 从简历中提取到 %d 个关键词: %s", len(resume_keywords), resume_keywords)
    # 提前为所有 provider 创建向量库，用于语义粗筛
    vectorstore = embed_resume(resume_text, "./vectorstores")
    
    # LLM 匹配分阈值，低于该分跳过不投；可用 BOSS_MIN_MATCH_SCORE 覆盖
    min_llm_score = int(os.getenv("BOSS_MIN_MATCH_SCORE", "50"))
    exclude_str = os.getenv("BOSS_EXCLUDE_KEYWORDS", "")
    exclude_keywords = [k.strip() for k in exclude_str.split(",") if k.strip()] if exclude_str else None

    await send_job_descriptions_to_chat(
        usr_name=usr_name,
        url=RECOMMEND_URL,
        browser_type="chrome",
        label=label,
        dry_run=dry_run,
        resume_keywords=resume_keywords,
        resume_text=resume_text,
        min_llm_score=min_llm_score,
        exclude_keywords=exclude_keywords,
        vectorstore=vectorstore,
    )


def _cli_main() -> None:
    """``python -m boss_zhipin`` / 根目录 ``main.py`` shim / pyproject script
    都委托到这个函数。

    把 ``load_dotenv`` 和 ``logging.basicConfig`` 收进来——``basicConfig``
    只有真正"以 CLI 方式跑"才生效，单纯 ``import boss_zhipin.cli`` 不会污染
    logging。（``.env`` 本身仍会在 import-time 经由 ``models.*`` 读入，见
    module docstring；这里的 ``load_dotenv()`` 是给"models 还没 import 就
    需要 env"的将来留的显式入口，幂等。）
    """
    load_dotenv()
    logging.basicConfig(
        level=os.getenv("LOGLEVEL", "INFO").upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    dry_run = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")
    if dry_run:
        print("⚠️  DRY_RUN=1 — 招呼语只会生成 + 写日志，不会真的发到 BOSS")

    ensure_llm_configured()
    usr_name = ensure_usr_name()
    resume_path = ensure_resume_path()
    label = get_label()
    if label:
        print(f"求职 tag：{label}")
    else:
        print("没设 BOSS_LABEL，用 BOSS 默认推荐 feed")

    # run_provider 是 async 的（整段必须跑在同一个事件循环里，否则 nodriver
    # CDP 会在 run_until_complete 之间进入半死态导致 evaluate hang）。
    # 这里用 ``uc.loop().run_until_complete(...)`` 一次性跑完。
    uc.loop().run_until_complete(
        run_provider(usr_name, label, dry_run, resume_path)
    )


if __name__ == "__main__":
    _cli_main()
