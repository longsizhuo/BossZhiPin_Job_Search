"""业务代码 → GUI 的事件总线。

业务代码（``website_oper/write_response.py`` 等）在关键节点调 ``emit(kind, **payload)``，
由当前注册的 callback 把事件路由到 GUI 框架（PyTauri Channel / 测试断言 / log）。

设计要点：
- **没装 pytauri 也能 import**。本模块只依赖 stdlib + pydantic。CLI 模式（main.py）
  不调 ``set_emit_callback``，emit() 自动是 no-op，业务代码行为零变化。
- **module-global callback，不用 ContextVar**。只允许同时跑一个 run（``gui.runner``
  的契约），所以不需要 ContextVar 的 task-local 隔离。简单一个全局变量够。
- ``ProgressEvent`` 是 Pydantic v2 model——PyTauri Channel 自动认 BaseModel
  做序列化，前端 TypeScript 端有相应类型。
"""
from __future__ import annotations

from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel

EventKind = Literal[
    "browser_started",   # Chrome 起来了
    "login_ok",          # 登录态确认
    "job_found",         # 抓到一个 JD，payload: {index, jd_preview}
    "job_skipped",       # 跳过当前岗位，payload: {index, reason, detail}
    "scoring_degraded",  # LLM 评分 fail-open（本轮全放行），payload: {detail}，每轮最多一次
    "letter_sent",       # 招呼语处理完成，payload: {index, status: "sent"|"dry_run"|"blocked"}
    "feed_exhausted",    # 推荐 feed 跑到底（连续 N 次拿不到 JD），payload: {total}
    "loop_ended",        # runner 包的整段结束，payload: {reason: "completed"|"cancelled"|"error"}
    "error",             # 任何阶段抛了未捕获异常，payload: {stage, message}
]


class ProgressEvent(BaseModel):
    """业务代码发给 GUI 的结构化事件。

    payload 是个 dict 而非每个 kind 一个子类，因为：
    - 事件类型少（个位数）
    - 前端用 switch/match 一处分发，子类反而要类型守卫
    - 加字段不破坏老代码
    """

    kind: EventKind
    payload: dict[str, Any] = {}


_emit_callback: Optional[Callable[[ProgressEvent], None]] = None


def set_emit_callback(cb: Optional[Callable[[ProgressEvent], None]]) -> None:
    """注册 callback。GUI 模式在 start_run 之前 set，结束后 clear。"""
    global _emit_callback
    _emit_callback = cb


def emit(kind: EventKind, **payload: Any) -> None:
    """业务代码的 emit 助手。callback=None 时（CLI 模式）静默 no-op。

    callback 抛异常不会传播——业务代码不应该因为 GUI 端的 bug 挂掉。
    """
    cb = _emit_callback
    if cb is None:
        return
    try:
        cb(ProgressEvent(kind=kind, payload=payload))
    except Exception:
        pass
