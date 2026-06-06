"""``gui/runner.py`` + ``gui/events.py`` + ``gui/log_bridge.py`` 的单测。

不依赖 NiceGUI / PyTauri / nodriver——直接用 ``asyncio.sleep`` 和 raise
模拟主循环，验证 runner 的状态机和 emit 路由正确。

项目没装 pytest-asyncio，每个用例自己用 ``asyncio.run`` 包一下。
"""
from __future__ import annotations

import asyncio
import logging

import pytest

from boss_zhipin.gui import events as gui_events
from boss_zhipin.gui import log_bridge
from boss_zhipin.gui import runner


@pytest.fixture(autouse=True)
def _reset_runner_state():
    """每个用例跑前后都重置模块级状态，避免互相污染。"""
    runner.reset()
    yield
    runner.reset()


def test_start_then_completes_emits_loop_ended_completed():
    async def scenario():
        events: list[gui_events.ProgressEvent] = []

        async def fast_loop():
            gui_events.emit("browser_started")

        task = runner.start_run(fast_loop, on_event=events.append)
        await task
        kinds = [e.kind for e in events]
        assert kinds == ["browser_started", "loop_ended"]
        assert events[-1].payload["reason"] == "completed"

    asyncio.run(scenario())


def test_start_twice_raises():
    async def scenario():
        async def slow_loop():
            await asyncio.sleep(10)

        runner.start_run(slow_loop)
        try:
            with pytest.raises(RuntimeError, match="already in progress"):
                runner.start_run(slow_loop)
        finally:
            await runner.stop_run()

    asyncio.run(scenario())


def test_stop_cancels_and_emits_cancelled():
    async def scenario():
        events: list[gui_events.ProgressEvent] = []
        started = asyncio.Event()

        async def loop_until_cancelled():
            gui_events.emit("browser_started")
            started.set()
            await asyncio.sleep(30)

        runner.start_run(loop_until_cancelled, on_event=events.append)
        await asyncio.wait_for(started.wait(), timeout=1.0)
        stopped = await runner.stop_run(timeout=5.0)
        assert stopped is True
        kinds = [e.kind for e in events]
        assert "browser_started" in kinds
        assert kinds[-1] == "loop_ended"
        assert events[-1].payload["reason"] == "cancelled"

    asyncio.run(scenario())


def test_stop_when_idle_returns_false():
    async def scenario():
        assert await runner.stop_run() is False

    asyncio.run(scenario())


def test_exception_emits_error_and_loop_ended():
    async def scenario():
        events: list[gui_events.ProgressEvent] = []

        async def crashing_loop():
            gui_events.emit("browser_started")
            raise ValueError("boom")

        task = runner.start_run(crashing_loop, on_event=events.append)
        await task  # runner swallows exception internally
        kinds = [e.kind for e in events]
        assert kinds == ["browser_started", "error", "loop_ended"]
        error_event = events[1]
        assert error_event.payload["stage"] == "main_loop"
        assert "ValueError" in error_event.payload["message"]
        assert "boom" in error_event.payload["message"]
        assert events[-1].payload["reason"] == "error"

    asyncio.run(scenario())


def test_emit_helper_noop_when_no_callback():
    """CLI 模式（没有 set_emit_callback）emit 必须 no-op，不抛。"""
    gui_events.emit("browser_started")
    gui_events.emit("job_found", index=3, jd_preview="后端")
    # 不抛即通过


def test_emit_callback_swallows_exceptions():
    """callback 抛异常不能传播给业务代码。"""
    def angry_cb(ev):
        raise RuntimeError("UI bug!")

    gui_events.set_emit_callback(angry_cb)
    try:
        gui_events.emit("browser_started")  # 不应抛
    finally:
        gui_events.set_emit_callback(None)


def test_callback_cleared_after_natural_completion():
    """run 自然结束（不靠 stop_run）后 emit 应该回到 no-op，
    防止下次 start_run 之前的旧 callback 还在收事件。"""
    async def scenario():
        events: list[gui_events.ProgressEvent] = []

        async def trivial():
            return

        task = runner.start_run(trivial, on_event=events.append)
        await task
        n_before = len(events)
        gui_events.emit("browser_started")  # 应该是 no-op
        assert len(events) == n_before

    asyncio.run(scenario())


def test_callback_cleared_after_cancel():
    """cancel 路径同样要清 callback。"""
    async def scenario():
        events: list[gui_events.ProgressEvent] = []
        started = asyncio.Event()

        async def slow():
            started.set()
            await asyncio.sleep(30)

        runner.start_run(slow, on_event=events.append)
        await started.wait()
        await runner.stop_run(timeout=2)
        n_before = len(events)
        gui_events.emit("browser_started")  # 应该是 no-op
        assert len(events) == n_before

    asyncio.run(scenario())


def test_pydantic_event_serializes():
    """ProgressEvent 是 Pydantic model，能 dump 成 dict 喂 PyTauri Channel。"""
    ev = gui_events.ProgressEvent(kind="job_found", payload={"index": 3, "jd_preview": "Hi"})
    d = ev.model_dump()
    assert d["kind"] == "job_found"
    assert d["payload"]["index"] == 3


def test_log_bridge_captures_logger_output():
    """log_bridge install 后，logging 调用必须出现在 callback 里。"""
    msgs: list[str] = []
    handler = log_bridge.install(msgs.append, level=logging.INFO)
    try:
        log = logging.getLogger("test_runner.bridge")
        log.setLevel(logging.INFO)
        log.info("hello bridge")
        assert any("hello bridge" in m for m in msgs)
    finally:
        log_bridge.uninstall(handler)


def test_log_bridge_install_replaces_previous():
    """重复 install 应卸掉旧 handler，否则同条日志被推 2 次。"""
    msgs1: list[str] = []
    msgs2: list[str] = []
    h1 = log_bridge.install(msgs1.append, level=logging.INFO)
    h2 = log_bridge.install(msgs2.append, level=logging.INFO)
    try:
        log = logging.getLogger("test_runner.replace")
        log.setLevel(logging.INFO)
        log.info("ping")
        assert len(msgs1) == 0
        assert len(msgs2) == 1
    finally:
        log_bridge.uninstall(h2)
        log_bridge.uninstall(h1)


def test_log_bridge_callback_exception_swallowed():
    """callback 抛异常不能让 logger 挂。"""
    def angry(msg):
        raise RuntimeError("UI bug")

    h = log_bridge.install(angry, level=logging.INFO)
    try:
        logging.getLogger("test_runner.angry").info("ping")  # 不应抛
    finally:
        log_bridge.uninstall(h)
