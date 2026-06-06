"""GUI 配置面板用——读/写 ``.env`` 表单字段。

只动 ``.env``，**不动 ``os.environ``**——避免 GUI 修改的字段污染同进程里
其他模块的读 env 操作（特别是 LLM client 在 import 时读 API key）。GUI
保存后用户需要重启 app 或重新 start_run 让新值生效。

API key 字段在前端 mask（password input），后端不主动 mask——前端拿到
真实值后用户改的时候不至于看到 ``***``。
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from dotenv import dotenv_values, set_key, unset_key

# 暴露给前端的配置字段。每一项映射 ``.env`` 里一个 key。
# 顺序决定前端表单顺序。
KNOWN_KEYS: list[tuple[str, str, bool]] = [
    # (env key, 字段说明, is_secret)
    ("DEEPSEEK_API_KEY", "DeepSeek API key", True),
    ("OPENAI_API_KEY", "OpenAI API key", True),
    ("ANTHROPIC_API_KEY", "Anthropic (Claude) API key", True),
    ("BOSS_USR_NAME", "你的名字（招呼语署名）", False),
    ("BOSS_LABEL", "求职 tag（空走 BOSS 推荐 feed）", False),
    ("RESUME_PATH", "简历 PDF 路径（默认 ./resume/my_cover.pdf）", False),
    ("CHATGPT_MODEL", "OpenAI 模型（默认 gpt-4o）", False),
    ("OPENAI_BASE_URL", "OpenAI 代理 URL（可选）", False),
    ("BOSS_CHROME_PROFILE", "Chrome profile 目录（默认 ./chrome_profile）", False),
    ("BOSS_MIN_MATCH_SCORE", "LLM 匹配分阈值（默认 50）", False),
    ("LOGLEVEL", "日志级别（默认 INFO）", False),
]


def _env_path() -> Path:
    return Path(".env")


def read_env() -> dict[str, str]:
    """返回 .env 里已经设了的 key → value。

    缺失文件返回空 dict。Comment 行 / 解析错误自动跳过。**只返回 KNOWN_KEYS
    里的字段**——其他字段（用户自己加的）不在前端表单里，也不让前端不小心
    覆盖掉。
    """
    path = _env_path()
    if not path.is_file():
        return {}
    raw = dotenv_values(path)
    return {k: v for k, v in raw.items() if v is not None and k in {kk for kk, _, _ in KNOWN_KEYS}}


def write_env(updates: dict[str, str]) -> None:
    """把表单提交的 key/value 写回 .env。

    - 空字符串 → ``unset_key`` 把那一行删掉（区别于"留空但保留 key"）
    - 不存在的 key 自动 append
    - 跟 read_env 一样**只允许 KNOWN_KEYS 里的字段**，防注入
    """
    path = _env_path()
    path.touch(exist_ok=True)
    allowed = {k for k, _, _ in KNOWN_KEYS}
    for k, v in updates.items():
        if k not in allowed:
            continue
        if v == "":
            try:
                unset_key(str(path), k)
            except Exception:
                pass
        else:
            set_key(str(path), k, v, quote_mode="never")


def field_meta() -> list[dict[str, str | bool]]:
    """给前端的 fields metadata（key / label / is_secret）。"""
    return [{"key": k, "label": label, "isSecret": is_secret}
            for k, label, is_secret in KNOWN_KEYS]
