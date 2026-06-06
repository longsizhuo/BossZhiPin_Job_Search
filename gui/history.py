"""GUI 历史面板用——读 ``logs/letters.jsonl``。

``audit.__init__`` 负责写，本模块负责读。分开是因为：
- ``audit`` 是 CLI 也用的业务模块，不应该 import 任何"列表读取/分页"逻辑
- 测试 ``audit.log_attempt`` 不需要测 read
- 未来历史面板想加过滤/分页/全文搜索，集中在这里
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _letters_path() -> Path:
    return Path(os.getenv("LETTER_LOG_PATH", "./logs/letters.jsonl"))


def read_letters(limit: int = 200) -> list[dict[str, Any]]:
    """读 letters.jsonl 最末尾 ``limit`` 条，最新的在 list 末尾。

    文件不存在 / 解析失败的行被跳过——前端面板不会因为一条坏数据整个崩。
    """
    path = _letters_path()
    if not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
