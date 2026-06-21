"""PyTauri 桌面 App 入口。

**两种运行模式**，靠 ``BOSS_TAURI_STANDALONE`` env var 区分：

1. **Wheel dev 模式**（默认）：``uv sync && uv run python -m boss_zhipin.tauri``。
   tauri 组在 ``[tool.uv].default-groups`` 里，``uv sync`` 默认就装上；CLI-only
   用户可以 ``uv sync --no-group tauri`` 跳过。Python 进程是主进程，
   ``pytauri-wheel`` 提供 Tauri Rust binary。Tauri.toml / capabilities /
   frontend 从本包 source 目录读。

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
    dry_run: bool = False
    resume_path: str = ""  # 空 → 用 RESUME_PATH env / 默认值


class StartRunBody(_CamelModel):
    config: RunConfig
    progress_channel: JavaScriptChannelId[ProgressEvent]
    log_channel: JavaScriptChannelId[str]


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

        # 同步到 env，业务代码深处读 env 的地方（DRY_RUN / RESUME_PATH 等）也能感知。
        # DRY_RUN 必须**显式清掉**：os.environ 是进程级、跨 run 复用的。只设不清
        # 的话，用户先勾 Dry-run 测一次留下 DRY_RUN=1，之后取消勾选真跑时，任何
        # call-time 读 os.getenv("DRY_RUN") 的地方仍判为 dry-run → 招呼语只生成不
        # 发送，且要重启 App 才好（非技术用户极难自查）。每次按当前勾选状态归位。
        if config.dry_run:
            environ["DRY_RUN"] = "1"
        else:
            environ.pop("DRY_RUN", None)
        environ["BOSS_USR_NAME"] = config.usr_name
        if config.resume_path:
            environ["RESUME_PATH"] = config.resume_path
        if config.label:
            environ["BOSS_LABEL"] = config.label

        resume_path = environ.get("RESUME_PATH", "").strip() or DEFAULT_RESUME_PATH

        # 简历预处理 + 主循环全部走 cli.run_provider——CLI 和 GUI 共用一份逻辑。
        # 用哪个 LLM 端点由 LLM_* env 决定（Config 页已存进 .env + os.environ）。
        await run_provider(
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
    - 没填用户名 → ``ValueError``
    - 找不到简历 → ``ValueError``
    - 没配 LLM key / model → ``ValueError``
    """
    from boss_zhipin.gui.i18n import msg

    if runner.is_running():
        raise RuntimeError(msg("err.already_running"))

    # 名字非空前置校验：usr_name 会作为招呼语署名直接传给业务代码，空字符串会
    # 让招呼语署名为空。跟简历校验一样在这里同步抛 ValueError，前端 catch 后
    # 秒级可见，而不是等跑起来才发现署名空了。
    if not body.config.usr_name.strip():
        raise ValueError(msg("err.need_name"))

    # 简历存在性前置校验：不查的话，缺简历会等 cli import（torch，~10s）跑完才在
    # run_provider 深处抛 FileNotFoundError，只剩 Progress 面板一行容易错过的
    # [error]，用户感受是"点开始没反应"。尤其 standalone .app 的 CWD 是应用数据
    # 目录，repo 里的 resume/ 不在那儿——这是缺省炸点。这里同步抛 ValueError，
    # pyInvoke 直接 reject，前端 catch 后写进日志面板，秒级可见。current_resume
    # 只做 is_file 判断，不触发重 import。
    from boss_zhipin.gui.resume_io import current_resume

    if current_resume() is None:
        raise ValueError(msg("err.need_resume"))

    # LLM 端点前置校验：缺 key 或缺 model 跑起来都会在 _build_client 深处抛
    # RuntimeError——而主循环的 except 会把它当一次性错误 break 掉整个 run（第一个
    # 岗位就挂）。这里提前拦，前端秒级可见。注意要连 model 一起查：只查 key 的话，
    # "填了 key 没填 model" 会通过校验，然后 generate_letter 在第一个岗位抛错收摊。
    from boss_zhipin.gui.llm_config import read_llm_config

    llm_cfg = read_llm_config()
    if not llm_cfg["hasKey"]:
        raise ValueError(msg("err.need_ai"))
    if not llm_cfg["model"]:
        raise ValueError(msg("err.need_model"))

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


# ---------- Config 面板：AI 端点（base_url + key + model） ----------


@commands.command()
async def get_llm_config() -> dict[str, object]:
    """返回端点选择器信息：``{baseUrl, model, hasKey, presets: [...]}``。

    真相源 os.environ 优先、回退 .env 文件（GUI 启动时 env 还没 load）——见
    ``gui.llm_config.read_llm_config`` 的说明。
    """
    from boss_zhipin.gui.llm_config import read_llm_config
    return read_llm_config()


class _LlmConfigBody(_CamelModel):
    base_url: str = ""
    model: str = ""
    api_key: str = ""  # 空 → 只改 base_url/model，不动已存的 key


@commands.command()
async def set_llm_config(body: _LlmConfigBody) -> dict[str, str]:
    """存端点配置（base_url + model + 可选 key）。"""
    from boss_zhipin.gui.llm_config import write_llm_config
    write_llm_config(body.base_url, body.model, body.api_key or None)
    return {"status": "saved"}


# ---------- Config 面板：通用字段 ----------


@commands.command()
async def get_env_fields() -> dict[str, list[dict]]:
    """返回前端 Config 表单的所有字段 + 当前值。

    返回 plain dict 列表，不要塞 pydantic BaseModel 实例——pytauri 的 IPC
    response 走 JSON 序列化，遇到未 ``model_dump`` 的 BaseModel 会卡住
    （promise 不 resolve 也不 reject），前端 Config 页一直显示"加载中…"。
    """
    from boss_zhipin.gui.env_io import field_meta, read_env

    current = read_env()
    return {
        "fields": [
            {**meta, "value": current.get(str(meta["key"]), "")}
            for meta in field_meta()
        ]
    }


class WriteEnvBody(_CamelModel):
    updates: dict[str, str]


@commands.command()
async def write_env_fields(body: WriteEnvBody) -> dict[str, str]:
    """把表单的修改写回 .env。"""
    from boss_zhipin.gui.env_io import write_env
    write_env(body.updates)
    return {"status": "saved"}


# ---------- Config 面板：UI 语言 ----------


@commands.command()
async def get_language() -> dict[str, str]:
    """返回存的 UI 语言（``{lang}``）。没设过返回空字符串，前端用系统探测的默认。"""
    from boss_zhipin.gui.env_io import read_language
    return {"lang": read_language()}


class _LanguageBody(_CamelModel):
    lang: str


@commands.command()
async def set_language(body: _LanguageBody) -> dict[str, str]:
    """存 UI 语言到 .env。只接受已知值（zh / en），其余忽略防注入。"""
    from boss_zhipin.gui.env_io import write_language
    if body.lang in ("zh", "en"):
        write_language(body.lang)
    return {"status": "saved"}


# ---------- 简历（Run 页拖拽上传） ----------


class _SetResumeBody(_CamelModel):
    path: str  # 前端拖拽事件给的绝对路径


@commands.command()
async def set_resume(body: _SetResumeBody) -> dict[str, str]:
    """把拖进来的 PDF 复制进 ``resume/`` 并设为当前简历。

    返回 ``{filename, path}``。校验失败（不是 PDF / 文件不存在）抛 ``ValueError``，
    PyTauri 自动序列化成前端 ``catch`` 能拿到的字符串。
    """
    from boss_zhipin.gui.resume_io import store_resume
    return store_resume(body.path)


class _SetResumeBytesBody(_CamelModel):
    filename: str       # 原文件名（只用 basename，决定落盘文件名）
    data_base64: str    # 文件字节的 base64（前端 <input type=file> 读出来编的）


@commands.command()
async def set_resume_bytes(body: _SetResumeBytesBody) -> dict[str, str]:
    """文件选择器（``<input type=file>``）选的 PDF → 存进 ``resume/`` 设为当前简历。

    webview 的 file input 给不到真实磁盘路径（安全限制），只能拿字节，所以走这条；
    拖拽上传仍走 ``set_resume``（那条有真实路径）。返回 ``{filename, path}``，
    校验失败抛 ``ValueError``。
    """
    import base64

    from boss_zhipin.gui.resume_io import store_resume_bytes
    return store_resume_bytes(body.filename, base64.b64decode(body.data_base64))


@commands.command()
async def get_resume() -> dict[str, Optional[dict]]:
    """返回当前简历 ``{resume: {filename, path}}``，没设置 / 文件不在则 ``resume`` 为 null。

    运行页一挂载就调，**不能触发重 import**——``resume_io.current_resume``
    刻意没 import cli/vectorization（torch），保持轻量。
    """
    from boss_zhipin.gui.resume_io import current_resume
    return {"resume": current_resume()}


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


# ---------- 检查更新（只提示，不自动下载） ----------


@commands.command()
async def check_for_update() -> dict[str, object]:
    """前端启动时调一次——查 GitHub 最新 release，返回是否有新版。

    返回 ``{current, latest, url, hasUpdate}``。``check_latest_release`` 永不抛
    异常（没网 / 限速静默降级成 hasUpdate=False），所以这里不用额外兜错。
    """
    from boss_zhipin.gui.updates import check_latest_release
    return check_latest_release()


class _OpenUrlBody(_CamelModel):
    url: str


@commands.command()
async def open_release_page(body: _OpenUrlBody) -> dict[str, str]:
    """用系统默认浏览器打开下载页——「前往下载」按钮调。

    只允许打开本仓库 releases 域下的 URL，避免前端被注入任意 URL 当跳板。
    """
    import webbrowser

    from boss_zhipin.gui.updates import REPO

    allowed_prefix = f"https://github.com/{REPO}/releases"
    target = body.url if body.url.startswith(allowed_prefix) else f"{allowed_prefix}/latest"
    webbrowser.open(target)
    return {"status": "opened"}


@commands.command()
async def open_issues_page() -> dict[str, str]:
    """用系统默认浏览器打开本仓库的"新建 issue"页——出错卡片的「打开 issues」调。

    URL 写死成本仓库 issues 域，前端传不进任意 URL。跟 ``open_release_page`` 一样
    只是个跳转，**不自动上报任何东西**——日志要不要发、发什么，全由用户手动决定。
    """
    import webbrowser

    from boss_zhipin.gui.updates import REPO

    webbrowser.open(f"https://github.com/{REPO}/issues/new")
    return {"status": "opened"}


class _AiHelpBody(_CamelModel):
    logs: list[str] = []  # 前端实时日志缓冲（store.logs），可空


@commands.command()
async def get_ai_help_report(body: _AiHelpBody) -> dict[str, str]:
    """「复制信息去问 AI」用——返回一段自带上下文的求助 markdown。

    把 app 介绍 + 版本/系统/配置体检 + 文档链接 + 最近日志打包，前端复制到剪贴板，
    用户粘到任意聊天 AI 就能对上号、拿到针对性帮助。绝不含 API key 明文。
    """
    from boss_zhipin.gui.diagnostics import build_ai_help
    return {"text": build_ai_help(body.logs)}


@commands.command()
async def get_log_dir() -> dict[str, str]:
    """返回日志目录的绝对路径，让用户知道去哪手动捞日志附到反馈里。

    项目没有持久 app.log（运行日志走 GUI 实时面板）；落盘的是 audit 的
    ``letters.jsonl`` 和 telemetry 的 ``llm_calls.jsonl``，都在这个目录下。
    """
    from boss_zhipin.audit import LOG_PATH

    return {"dir": str(LOG_PATH.parent.resolve())}


def main() -> int:
    """启动 PyTauri app——根据 BOSS_TAURI_STANDALONE 自动切换 wheel / standalone。"""
    if BOSS_STANDALONE:
        # .app 双击启动时 CWD 是 ``/``，所有相对默认路径（logs/ vectorstores/
        # chrome_profile/ .env resume/）都会落错地方。入口处统一 chdir 到
        # 平台应用数据目录，business 代码不用感知。必须在任何业务 import
        # （models.* 的 load_dotenv 是 import-time）之前做。
        from boss_zhipin.paths import ensure_app_data_cwd
        data_dir = ensure_app_data_cwd()

    logging.basicConfig(
        level=environ.get("LOGLEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if BOSS_STANDALONE:
        log.info("standalone 模式：数据目录 %s", data_dir)
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
