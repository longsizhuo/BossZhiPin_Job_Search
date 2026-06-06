"""本地 Web GUI（NiceGUI），跟 CLI ``main.py`` 平行的入口。

跑：``uv run boss-gui`` 或 ``uv run python -m gui``。

设计：
- 复用 ``main.py`` 的 provider 检测、``website_oper`` 的所有 async helper、
  ``audit`` 的招呼语校验。
- 通过 ``gui.events.current_progress`` ContextVar 把进度事件注入业务代码，
  CLI 模式 sink=None 时业务代码行为完全不变。
- ``gui.log_bridge`` 把 root logger 的输出桥接到 asyncio.Queue，给 UI 的
  ``ui.log`` 控件订阅。

关键约束（见 ``project-nicegui-uvloop-incompat`` memory）：
- ``ui.run()`` 必须传 ``loop="asyncio"``，否则 nodriver 的 Chrome 重启会 timeout。
- ``ui.run()`` 必须 ``reload=False``，否则 Chrome 子进程会变孤儿。
"""
