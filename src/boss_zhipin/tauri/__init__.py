"""PyTauri 桌面 App 入口。

**两种运行模式**，靠 ``BOSS_TAURI_STANDALONE`` env var 区分：

1. **Wheel dev 模式**（默认）：``uv sync --extra tauri && uv run python -m
   boss_zhipin.tauri``。Python 进程是主进程，``pytauri-wheel`` 提供 Tauri
   Rust binary。Tauri.toml / capabilities / frontend 从本包 source 目录读。

2. **Standalone 模式**（Phase D 打包后的 .app）：Rust binary 是主进程，
   embed Python interpreter，启动时 set ``BOSS_TAURI_STANDALONE=1``，再
   ``PythonScript::Module("boss_zhipin.tauri")`` 进入 ``__main__.py`` → 这里的
   ``main()``。Tauri.toml / capabilities / frontend 已经在编译期通过
   ``tauri::generate_context!()`` 嵌进 Rust binary，Python 不再读。

跟 CLI（``boss_zhipin.cli``）平行存在；CLI 模式完全不动。

业务代码（``website_oper`` / ``audit``）**完全不知道有 Tauri 这层**：
- 进度事件通过 ``gui.events.set_emit_callback`` 注入到 PyTauri Channel
- 日志通过 ``gui.log_bridge.install`` 注入到 PyTauri Channel
- 主循环还是 ``website_oper.write_response.send_job_descriptions_to_chat``

**关键约束**（见 project memory）：
- `start_blocking_portal("asyncio")` —— 不能默认 trio/uvloop，否则 nodriver
  重启 Chrome 会 timeout。
- ``capabilities/default.toml``（wheel）/ ``capabilities/default.json``
  （standalone）必须 grant ``pytauri:default``，否则前端 ``pyInvoke`` 被 ACL 拦。
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

from boss_zhipin.gui import log_bridge, runner
from boss_zhipin.gui.events import ProgressEvent

SRC_TAURI_DIR = Path(__file__).parent.absolute()
BOSS_DEV = environ.get("BOSS_TAURI_DEV") == "1"
BOSS_STANDALONE = environ.get("BOSS_TAURI_STANDALONE") == "1"

log = logging.getLogger(__name__)

commands = Commands()


class _CamelModel(BaseModel):
    """前端 TS 用 camelCase，Python 用 snake_case。"""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class RunConfig(_CamelModel):
    """``start_run`` 的参数。

    字段对齐 ``boss_zhipin.cli`` 走 CLI 时收集的东西。空字符串 / None 走跟
    CLI 一样的默认（比如 label 空时用 BOSS 默认推荐 feed）。
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

    复用 ``boss_zhipin.cli:detect_providers``，避免 CLI 和 GUI 行为分叉。
    """
    # 延迟 import，避免本模块在 CLI 测试里被意外引入
    from boss_zhipin.cli import detect_providers as _detect_providers  # noqa: WPS433

    return {"providers": _detect_providers()}


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
        # 延迟 import，让没装 ``tauri`` 可选依赖时 import boss_zhipin.tauri 不立即炸。
        from boss_zhipin.cli import DEFAULT_RESUME_PATH, run_provider

        # 同步到 env，业务代码深处读 env 的地方（DRY_RUN / RESUME_PATH 等）也能感知
        if config.dry_run:
            environ["DRY_RUN"] = "1"
        environ["BOSS_USR_NAME"] = config.usr_name
        if config.resume_path:
            environ["RESUME_PATH"] = config.resume_path
        if config.label:
            environ["BOSS_LABEL"] = config.label

        resume_path = environ.get("RESUME_PATH", "").strip() or DEFAULT_RESUME_PATH

        # 简历预处理 + provider 路由全部走 cli.run_provider——CLI 和 GUI
        # 共用一份逻辑，避免行为分叉。unknown provider 由它抛 ValueError。
        await run_provider(
            provider=config.provider,
            usr_name=config.usr_name,
            label=config.label,
            dry_run=config.dry_run,
            resume_path=resume_path,
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
    from boss_zhipin.website_oper import finding_jobs
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
    from boss_zhipin.gui.env_io import field_meta, read_env

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
    from boss_zhipin.gui.env_io import write_env
    write_env(body.updates)
    return {"status": "saved"}


# ---------- History 面板 ----------


class _LimitBody(_CamelModel):
    limit: int = 200


@commands.command()
async def get_letters(body: _LimitBody) -> dict[str, list[dict]]:
    """读 ``logs/letters.jsonl`` 末尾 ``limit`` 条。"""
    from boss_zhipin.gui.history import read_letters
    return {"letters": read_letters(limit=body.limit)}


@commands.command()
async def get_telemetry_summary() -> dict[str, dict]:
    """LLM 调用成本聚合。"""
    from boss_zhipin.audit.telemetry import telemetry_summary
    return {"summary": telemetry_summary(since_records=1000)}


def main() -> int:
    """启动 PyTauri app——根据 BOSS_TAURI_STANDALONE 自动切换 wheel / standalone。"""
    logging.basicConfig(
        level=environ.get("LOGLEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if BOSS_STANDALONE:
        # Standalone：Rust binary 已经 register 了 ext_mod，pytauri.builder_factory
        # / pytauri.context_factory 直接可用；Tauri.toml 已经被 generate_context!
        # 宏 inline 进 Rust binary，不需要再从 source 目录读，context_factory 无参。
        from pytauri import builder_factory, context_factory
        ctx = context_factory()
    else:
        # Wheel dev 模式：pytauri-wheel 内部维护自己的 Rust binary，需要把
        # Tauri.toml 所在目录传给 context_factory 让它在运行时读。
        from pytauri_wheel.lib import builder_factory, context_factory
        tauri_config: Optional[dict] = (
            {"build": {"frontendDist": "http://localhost:1420"}} if BOSS_DEV else None
        )
        ctx = context_factory(SRC_TAURI_DIR, tauri_config=tauri_config)

    with start_blocking_portal("asyncio") as portal:
        app = builder_factory().build(
            context=ctx,
            invoke_handler=commands.generate_handler(portal),
        )
        return app.run_return()
