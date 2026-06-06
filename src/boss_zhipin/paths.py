"""落盘路径的统一解析——解决 standalone .app 的 CWD 问题。

项目里所有默认落盘路径（``./chrome_profile`` / ``./logs`` / ``./vectorstores``
/ ``.env`` / ``resume/my_cover.pdf``）都是 **CWD 相对**的：

- **repo / CLI 模式**（默认）：CWD 就是 repo root，历史行为，一切不变。
  CLAUDE.md 红线：不改现有用户 ``chrome_profile`` 的默认位置。
- **standalone 模式**（Phase D 的 .app，``BOSS_TAURI_STANDALONE=1``）：
  双击启动时 CWD 是 ``/``，相对路径全废。解法不是逐个改业务代码里的
  路径，而是入口处 ``ensure_app_data_cwd()`` 一次性把 CWD 切到平台
  应用数据目录（macOS: ``~/Library/Application Support/<identifier>``），
  让所有相对默认值原样生效。

env var 覆盖（``BOSS_CHROME_PROFILE`` / ``LETTER_LOG_PATH`` /
``RESUME_PATH`` ...）依旧优先——绝对路径不受 chdir 影响。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 跟 src-tauri/tauri.conf.json 的 identifier 保持一致
APP_IDENTIFIER = "com.longsizhuo.boss-zhipin"


def is_standalone() -> bool:
    """是否运行在 Phase D standalone .app 里（Rust 主进程 set 的 env var）。"""
    return os.environ.get("BOSS_TAURI_STANDALONE") == "1"


def app_data_dir() -> Path:
    """平台应用数据目录。``BOSS_APP_DATA_DIR`` env 可覆盖（也方便测试）。"""
    override = os.environ.get("BOSS_APP_DATA_DIR", "").strip()
    if override:
        return Path(override)
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / APP_IDENTIFIER


def ensure_app_data_cwd() -> Path:
    """standalone 入口调：建好数据目录并 chdir 进去，返回该目录。

    之后所有 CWD 相对的默认路径（logs/ vectorstores/ chrome_profile/ .env
    resume/）都自动落在数据目录下。非 standalone 模式**不要**调它。
    """
    data_dir = app_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(data_dir)
    return data_dir
