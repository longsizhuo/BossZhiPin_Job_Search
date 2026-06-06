"""GUI 层共享工具——给 ``boss_tauri`` (PyTauri 桌面 App) 用，**不依赖** PyTauri 本身。

CLI ``main.py`` 不调本包；CLI 行为不受 ``gui/`` 任何代码影响。

模块清单：

- ``events`` —— ``ProgressEvent`` (Pydantic) + ``emit(kind, **payload)``。业务代码
  ``website_oper.write_response`` 在关键节点调 ``emit()``；callback=None 时 no-op，
  CLI 模式行为零变化。GUI 入口用 ``set_emit_callback`` 注册一个 PyTauri Channel
  send 函数即可订阅。
- ``runner`` —— ``start_run(coro_factory, on_event)`` / ``stop_run()`` /
  ``is_running()``，把主循环包成可取消 asyncio Task，task 内 emit
  ``loop_ended(reason)``。
- ``log_bridge`` —— ``CallbackHandler`` 把 ``logging.LogRecord`` 喂给 callback。
- ``env_io`` —— 读/写 ``.env`` 表单字段（GUI Config tab 用）。
- ``history`` —— 读 ``logs/letters.jsonl`` 末尾 N 条（GUI History tab 用）。

桌面 App 入口在 ``boss_tauri/__init__.py``：``uv sync --extra tauri`` 后
``uv run python -m boss_tauri``。

关键约束（见 ``project-nicegui-uvloop-incompat`` memory）：
- PyTauri 起 app 时必须 ``start_blocking_portal("asyncio")``，不能 trio /
  uvloop——uvloop 跟 nodriver 的 Chrome stop+restart 不兼容。
- ``boss_tauri/capabilities/default.toml`` 必须 grant ``pytauri:default``，
  否则前端 ``pyInvoke`` 全部被 Tauri ACL 拦。
"""
