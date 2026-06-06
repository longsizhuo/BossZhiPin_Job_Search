"""把主循环包成一个可取消的 asyncio Task，并把进度事件路由到注册的 callback。

为什么需要这一层：
- ``website_oper.write_response.send_job_descriptions_to_chat`` 是 async 函数，
  GUI 入口必须用 ``asyncio.create_task(...)`` 挂到当前 running loop。
- "停止"按钮要能取消，所以需要拿到 Task 引用调 ``task.cancel()``。
- 取消时要 emit ``loop_ended(reason="cancelled")`` 让 UI 显示干净的"已停止"。

设计上**不直接 import** ``send_job_descriptions_to_chat``——接受 ``coro_factory``
（无参 → coroutine 的工厂）。这样：
- 测试可以传 ``lambda: asyncio.sleep(60)`` 不依赖 nodriver
- PyTauri command 在 ``src-tauri/python/`` 里 partial 出 factory，把表单参数绑进去
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional

from boss_zhipin.gui.events import ProgressEvent, emit, set_emit_callback

log = logging.getLogger(__name__)

_task: Optional[asyncio.Task] = None


def is_running() -> bool:
    return _task is not None and not _task.done()


def get_task() -> Optional[asyncio.Task]:
    """主要给测试用——生产代码应该用 ``is_running()``。"""
    return _task


async def _wrap(coro: Awaitable[None]) -> None:
    """业务 coroutine 外壳：catch 异常 + emit loop_ended + 清 callback。"""
    try:
        try:
            await coro
            emit("loop_ended", reason="completed")
        except asyncio.CancelledError:
            emit("loop_ended", reason="cancelled")
            raise  # 必须继续传，否则 Task 不会真正 cancelled
        except Exception as e:
            log.exception("runner: main loop crashed")
            emit("error", stage="main_loop", message=f"{type(e).__name__}: {e}")
            emit("loop_ended", reason="error")
    finally:
        # 不管是自然结束、cancel、还是异常，都要清 callback——避免下一次 start_run
        # 之前的旧 callback 还在收事件。
        set_emit_callback(None)


def start_run(
    coro_factory: Callable[[], Awaitable[None]],
    on_event: Optional[Callable[[ProgressEvent], None]] = None,
) -> asyncio.Task:
    """启动一次新的运行。

    ``on_event`` 是事件 sink。GUI 模式传 PyTauri Channel 的 send；测试可以
    收集到 list 里断言。None 时业务代码 ``emit()`` 是 no-op。

    已有运行时抛 ``RuntimeError``，避免双开覆盖。
    """
    global _task
    if is_running():
        raise RuntimeError("a run is already in progress")
    set_emit_callback(on_event)
    _task = asyncio.create_task(_wrap(coro_factory()))
    return _task


async def stop_run(timeout: float = 30.0) -> bool:
    """取消当前 task 并等它退出。返回 False 表示当时没在跑（idempotent）。

    timeout 内没退出返回 True，但 task 可能仍在跑——通常因为底层 LLM 同步
    HTTP 请求 in flight，没办法被 cancel 立刻打断。

    本函数**不**关 Chrome。Chrome 在 GUI 进程生命周期内保持启动，下一次
    ``start_run`` 直接复用 cookie。需要彻底关 Chrome 调
    ``website_oper.finding_jobs.shutdown()``。
    """
    global _task
    if not is_running():
        return False
    assert _task is not None
    _task.cancel()
    try:
        await asyncio.wait_for(_task, timeout=timeout)
    except asyncio.CancelledError:
        pass
    except asyncio.TimeoutError:
        log.warning("runner: task didn't exit within %.1fs of cancel", timeout)
    except Exception:
        log.exception("runner: task raised during shutdown")
    finally:
        set_emit_callback(None)
    return True


def reset() -> None:
    """主要给测试用——清掉模块级 _task 引用 + emit callback。"""
    global _task
    _task = None
    set_emit_callback(None)
