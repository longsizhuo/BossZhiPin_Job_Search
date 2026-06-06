"""PyTauri 桌面 App 入口。

跑：``uv sync --extra tauri && uv run python -m boss_tauri``

跟 CLI（``main.py``）平行存在；CLI 模式完全不动。本模块对外暴露三件事：

- ``commands``：PyTauri ``Commands`` 实例，注册了 ``start_run`` / ``stop_run`` /
  ``is_running`` / ``detect_providers`` 这些前端能调的命令。
- ``main()``：起 PyTauri app 的入口。
- 各个 ``@commands.command()`` 函数本身——单测可以直接调（不通过 IPC）。

业务代码（``website_oper`` / ``audit``）**完全不知道有 Tauri 这层**：
- 进度事件通过 ``gui.events.set_emit_callback`` 注入到 PyTauri Channel
- 日志通过 ``gui.log_bridge.install`` 注入到 PyTauri Channel
- 主循环还是 ``website_oper.write_response.send_job_descriptions_to_chat``

**关键约束**（见 project memory）：
- `start_blocking_portal("asyncio")` —— 不能默认 trio/uvloop，否则 nodriver
  重启 Chrome 会 timeout。
- ``capabilities/default.toml`` 必须 grant ``pytauri:default``，否则前端的
  ``pyInvoke`` 会被 Tauri ACL 拦。
"""
from os import environ
from pathlib import Path

# pytauri 多 example 共存时用，单 example 不需要——保留以匹配官方模板。
environ.setdefault("_PYTAURI_DIST", "pytauri-wheel")

import asyncio
import functools
import logging
from typing import Optional

from anyio.from_thread import start_blocking_portal
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from pytauri import Commands
from pytauri.ipc import Channel, JavaScriptChannelId
from pytauri.webview import WebviewWindow
from pytauri_wheel.lib import builder_factory, context_factory

from gui import log_bridge, runner
from gui.events import ProgressEvent

SRC_TAURI_DIR = Path(__file__).parent.absolute()
BOSS_DEV = environ.get("BOSS_TAURI_DEV") == "1"

log = logging.getLogger(__name__)

commands = Commands()


class _CamelModel(BaseModel):
    """前端 TS 用 camelCase，Python 用 snake_case。"""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class RunConfig(_CamelModel):
    """``start_run`` 的参数。

    字段对齐 ``main.py`` 走 CLI 时收集的东西。空字符串 / None 走跟 CLI
    一样的默认（比如 label 空时用 BOSS 默认推荐 feed）。
    """
    usr_name: str
    label: str = ""
    provider: str  # "deepseek" / "chatgpt" / "claude"
    dry_run: bool = False
    resume_path: str = ""  # 空 → 用 RESUME_PATH env / 默认值


class StartRunBody(_CamelModel):
    config: RunConfig
    progress_channel: JavaScriptChannelId[ProgressEvent]
    log_channel: JavaScriptChannelId[str]


@commands.command()
async def detect_providers() -> dict[str, list[str]]:
    """前端用来填 provider 下拉——返回当前 env 里配了哪些 API key。

    复用 ``main.py:detect_providers``，避免 CLI 和 GUI 行为分叉。
    """
    # 延迟 import，避免本模块在 CLI 测试里被意外引入
    import main  # noqa: WPS433

    return {"providers": main.detect_providers()}


@commands.command()
async def is_running() -> dict[str, bool]:
    """前端轮询用——返回当前 run 是否还活着。"""
    return {"running": runner.is_running()}


def _build_main_loop_factory(config: RunConfig):
    """把 RunConfig + env var 折叠成一个无参的 coroutine 工厂。

    工厂调用时（runner.start_run 内部）才真正 import 业务代码 + 构造
    LLM client + 跑 vectorization。这一切都在主 portal loop 里跑，nodriver
    要求的"同一 loop"约束满足。
    """
    async def factory():
        # 延迟 import，让没装 ``tauri`` 可选依赖时 import boss_tauri 不立即炸。
        from main import RECOMMEND_URL, PROVIDER_ENV_KEYS
        from vectorization import embed_pdf
        from website_oper.write_response import send_job_descriptions_to_chat
        from models.job_matcher import extract_keywords_from_text, extract_resume_text

        # 同步到 env，业务代码深处读 env 的地方（DRY_RUN / RESUME_PATH 等）也能感知
        if config.dry_run:
            environ["DRY_RUN"] = "1"
        environ["BOSS_USR_NAME"] = config.usr_name
        if config.resume_path:
            environ["RESUME_PATH"] = config.resume_path
        if config.label:
            environ["BOSS_LABEL"] = config.label

        provider = config.provider
        if provider not in PROVIDER_ENV_KEYS:
            raise ValueError(f"unknown provider: {provider!r}")

        # 简历预处理（跟 CLI 入口顺序一致）
        resume_path = environ.get("RESUME_PATH", "").strip() or "resume/my_cover.pdf"
        resume_text = extract_resume_text(resume_path)
        resume_keywords = extract_keywords_from_text(resume_text)
        min_llm_score = int(environ.get("BOSS_MIN_MATCH_SCORE", "50"))

        common_kwargs = dict(
            usr_name=config.usr_name,
            url=RECOMMEND_URL,
            browser_type="chrome",
            label=config.label,
            dry_run=config.dry_run,
            resume_keywords=resume_keywords,
            resume_text=resume_text,
            min_llm_score=min_llm_score,
        )

        if provider == "chatgpt":
            # OpenAI 走 Assistants API，需要 client + assistant_id
            from openai import OpenAI
            from models.openai_assistant import OPENAI_API_KEY, create_assistant

            chatgpt_model = environ.get("CHATGPT_MODEL", "").strip() or "gpt-4o"
            openai_base_url = environ.get("OPENAI_BASE_URL", "").strip()
            client_openai = OpenAI(
                api_key=OPENAI_API_KEY,
                base_url=openai_base_url or None,
            )
            assistant_id = create_assistant(
                config.usr_name, chatgpt_model, client_openai, resume_path=resume_path
            )
            await send_job_descriptions_to_chat(
                models="chatgpt",
                client_openAI=client_openai,
                assistant_id=assistant_id,
                **common_kwargs,
            )
        else:
            # deepseek / claude 走 RAG，需要 vectorstore
            vectorstore = embed_pdf(resume_path, "./vectorstores")
            await send_job_descriptions_to_chat(
                models=provider,
                vectorstore=vectorstore,
                **common_kwargs,
            )

    return factory


@commands.command()
async def start_run(body: StartRunBody, webview_window: WebviewWindow) -> dict[str, str]:
    """前端 ``pyInvoke('start_run', { config, progressChannel, logChannel })`` 调。

    立刻返回 ``{status: "started"}``；进度通过 progress channel 推，日志通过
    log channel 推，前端订阅那两个 channel 自己消费。

    报错：
    - already running → ``RuntimeError`` 由 PyTauri 自动序列化成前端 ``catch`` 能拿到的字符串
    - bad provider → ``ValueError``
    """
    if runner.is_running():
        raise RuntimeError("already running")

    progress_channel = body.progress_channel.channel_on(webview_window.as_ref_webview())
    log_channel = body.log_channel.channel_on(webview_window.as_ref_webview())

    # 进度事件 → Channel
    def on_event(ev: ProgressEvent) -> None:
        try:
            progress_channel.send_model(ev)
        except Exception:
            pass

    # logging → Channel
    log_handler = log_bridge.install(lambda msg: _safe_send(log_channel, msg))

    factory = _build_main_loop_factory(body.config)

    # 包一层：run 结束后卸 log handler
    async def factory_with_cleanup():
        try:
            await factory()
        finally:
            log_bridge.uninstall(log_handler)

    runner.start_run(factory_with_cleanup, on_event=on_event)
    return {"status": "started"}


def _safe_send(channel, msg: str) -> None:
    try:
        channel.send(msg)
    except Exception:
        pass


@commands.command()
async def stop_run() -> dict[str, str]:
    """前端 stop 按钮调。idempotent——没在跑也不报错。"""
    stopped = await runner.stop_run(timeout=30.0)
    return {"status": "stopped" if stopped else "idle"}


@commands.command()
async def shutdown_browser() -> dict[str, str]:
    """关 Chrome——给"完全重置"按钮用。stop_run 之后再调这个才能从头来。"""
    from website_oper import finding_jobs
    await finding_jobs.shutdown()
    return {"status": "ok"}


# ---------- Config 面板 ----------


class EnvField(_CamelModel):
    key: str
    label: str
    is_secret: bool
    value: str


@commands.command()
async def get_env_fields() -> dict[str, list[EnvField]]:
    """返回前端 Config 表单的所有字段 + 当前值。"""
    from gui.env_io import field_meta, read_env

    current = read_env()
    fields = [
        EnvField(
            key=meta["key"],  # type: ignore[arg-type]
            label=meta["label"],  # type: ignore[arg-type]
            is_secret=bool(meta["isSecret"]),
            value=current.get(meta["key"], ""),  # type: ignore[arg-type]
        )
        for meta in field_meta()
    ]
    return {"fields": fields}


class WriteEnvBody(_CamelModel):
    updates: dict[str, str]


@commands.command()
async def write_env_fields(body: WriteEnvBody) -> dict[str, str]:
    """把表单的修改写回 .env。"""
    from gui.env_io import write_env
    write_env(body.updates)
    return {"status": "saved"}


# ---------- History 面板 ----------


class _LimitBody(_CamelModel):
    limit: int = 200


@commands.command()
async def get_letters(body: _LimitBody) -> dict[str, list[dict]]:
    """读 ``logs/letters.jsonl`` 末尾 ``limit`` 条。"""
    from gui.history import read_letters
    return {"letters": read_letters(limit=body.limit)}


@commands.command()
async def get_telemetry_summary() -> dict[str, dict]:
    """LLM 调用成本聚合。"""
    from audit.telemetry import telemetry_summary
    return {"summary": telemetry_summary(since_records=1000)}


def main() -> int:
    """启动 PyTauri app。"""
    logging.basicConfig(
        level=environ.get("LOGLEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    with start_blocking_portal("asyncio") as portal:
        if BOSS_DEV:
            tauri_config: Optional[dict] = {
                "build": {"frontendDist": "http://localhost:1420"},
            }
        else:
            tauri_config = None

        app = builder_factory().build(
            context=context_factory(SRC_TAURI_DIR, tauri_config=tauri_config),
            invoke_handler=commands.generate_handler(portal),
        )
        return app.run_return()
