"""BOSS Zhipin 自动招呼语脚本——可安装 Python 包。

调用入口：

- **CLI**：``python -m boss_zhipin`` 或 ``boss-zhipin``（pyproject 注册的 console script）
  或者根目录的 ``main.py`` shim（向后兼容 ``uv run main.py``）。
- **桌面 App（dev）**：``python -m boss_zhipin.tauri``（``uv sync`` 默认就装上 tauri 组）。
- **桌面 App（standalone .app）**：Phase D 用 pytauri standalone 把整个 ``boss_zhipin``
  包嵌进 embedded Python interpreter，前端通过 PyTauri IPC 调本包的 commands。

模块组织：

- ``audit/`` —— 招呼语校验 + 落盘日志 + LLM 调用 telemetry。
- ``models/`` —— LLM 客户端、prompts、岗位匹配评分。
- ``website_oper/`` —— nodriver-based BOSS 浏览器自动化。
- ``vectorization`` —— 简历 PDF → chroma 向量化 + 召回。
- ``utils/`` —— 通用工具（retry 装饰器等）。
- ``gui/`` —— 桌面 App 用的事件总线 / runner / log bridge / .env IO / 历史读取。
- ``tauri/`` —— PyTauri 桌面 App 入口（含 commands、Tauri.toml、capabilities）。
- ``cli`` —— 命令行入口；``__main__`` 委托给它。
"""
