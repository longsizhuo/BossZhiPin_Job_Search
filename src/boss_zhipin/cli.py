"""CLI 入口。

启动流程：
1. 读 ``.env``，根据有哪些 provider key 自动选用（一个直接用，多个让用户选）。
2. 兜底 ``BOSS_USR_NAME`` / ``BOSS_LABEL`` / ``RESUME_PATH`` 三个可选配置：
   不设就 prompt 用户输入或用默认值。
3. 按 provider 走 deepseek / chatgpt / claude 三条分支之一，进入主循环。

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
from openai import OpenAI

from boss_zhipin.models.job_matcher import extract_keywords_from_text, extract_resume_text
from boss_zhipin.models.openai_assistant import OPENAI_API_KEY, create_assistant
# PROVIDER_ENV_KEYS / PROVIDER_SIGNUP / detect_providers 抽到 boss_zhipin.providers
# 让 PyTauri 的 detect_providers 命令不被 cli.py 的重 import 链拖累
# （cli 的 vectorization import 会触发 sentence_transformers → torch，3-10s）。
from boss_zhipin.providers import (
    PROVIDER_ENV_KEYS,
    PROVIDER_SIGNUP,
    detect_providers,
)
from boss_zhipin.vectorization import embed_pdf
from boss_zhipin.website_oper.write_response import send_job_descriptions_to_chat

log = logging.getLogger(__name__)

# BOSS 推荐 feed 入口。CLI 和 GUI 都从这里进。
RECOMMEND_URL = "https://www.zhipin.com/web/geek/job-recommend?ka=header-job-recommend"

# 简历默认路径。CLI（ensure_resume_path）和 GUI（tauri 的 factory）共用。
DEFAULT_RESUME_PATH = "resume/my_cover.pdf"

__all__ = [
    "PROVIDER_ENV_KEYS",
    "PROVIDER_SIGNUP",
    "detect_providers",
    "RECOMMEND_URL",
    "DEFAULT_RESUME_PATH",
    "pick_provider",
    "ensure_usr_name",
    "ensure_resume_path",
    "run_provider",
]


def pick_provider() -> str:
    available = detect_providers()
    if not available:
        print("❌ 没在环境里找到任何 LLM provider 的 API key。")
        print("   去这些地方申请一个填进 .env（仓库里有 .env.example 可以参考）：")
        for name, url in PROVIDER_SIGNUP.items():
            print(f"     • {PROVIDER_ENV_KEYS[name]:<22} {url}")
        sys.exit(1)
    if len(available) == 1:
        provider = available[0]
        print(f"✅ 检测到只配了 {PROVIDER_ENV_KEYS[provider]}，自动选用：{provider}")
        return provider
    print(f"检测到 {len(available)} 个 provider 都配了 key，请选一个：")
    for i, name in enumerate(available, 1):
        print(f"  {i}. {name:<10} ({PROVIDER_ENV_KEYS[name]})")
    while True:
        choice = input(f"输入序号 (1-{len(available)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(available):
            return available[int(choice) - 1]
        print("无效输入，再试一次")


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
    provider: str,
    usr_name: str,
    label: str,
    dry_run: bool,
    resume_path: str,
) -> None:
    """简历预处理 + provider 路由 + 主循环，CLI 和 GUI 共用的唯一入口。

    路由规则（改这里就同时影响 CLI 和桌面 App，不会分叉）：
    - ``chatgpt`` 走 OpenAI Assistants API（client + assistant_id）
    - ``deepseek`` / ``claude`` 走 RAG（chroma vectorstore）

    必须在同一个事件循环里 await（nodriver CDP 跨 run_until_complete 会半死，
    见 ``_cli_main`` 的注释）。
    """
    if provider not in PROVIDER_ENV_KEYS:
        raise ValueError(f"unknown provider: {provider!r}")

    # 从简历自动提取关键词和全文（用于职位匹配过滤）
    resume_text = extract_resume_text(resume_path)
    resume_keywords = extract_keywords_from_text(resume_text)
    log.info("📋 从简历中提取到 %d 个关键词: %s", len(resume_keywords), resume_keywords)
    # LLM 匹配分阈值，低于该分跳过不投；可用 BOSS_MIN_MATCH_SCORE 覆盖
    min_llm_score = int(os.getenv("BOSS_MIN_MATCH_SCORE", "50"))

    common_kwargs = dict(
        usr_name=usr_name,
        url=RECOMMEND_URL,
        browser_type="chrome",
        label=label,
        dry_run=dry_run,
        resume_keywords=resume_keywords,
        resume_text=resume_text,
        min_llm_score=min_llm_score,
    )

    if provider == "chatgpt":
        chatgpt_model = os.getenv("CHATGPT_MODEL", "").strip() or "gpt-4o"
        log.info("OpenAI 模型：%s（可用 CHATGPT_MODEL 环境变量覆盖）", chatgpt_model)
        openai_base_url = os.getenv("OPENAI_BASE_URL", "").strip()
        if openai_base_url:
            log.info("OpenAI base_url 覆盖：%s", openai_base_url)
        client_openai = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=openai_base_url or None,
        )
        assistant_id = create_assistant(
            usr_name, chatgpt_model, client_openai, resume_path=resume_path
        )
        await send_job_descriptions_to_chat(
            models="chatgpt",
            client_openAI=client_openai,
            assistant_id=assistant_id,
            **common_kwargs,
        )
    else:
        # deepseek / claude：除了 provider 名，调用完全一致
        vectorstore = embed_pdf(resume_path, "./vectorstores")
        await send_job_descriptions_to_chat(
            models=provider,
            vectorstore=vectorstore,
            **common_kwargs,
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

    provider = pick_provider()
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
        run_provider(provider, usr_name, label, dry_run, resume_path)
    )


if __name__ == "__main__":
    _cli_main()
