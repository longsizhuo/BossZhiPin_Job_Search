"""GUI 配置面板用——读/写 ``.env`` 表单字段。

写 ``.env`` 的同时**也同步进程内的 ``os.environ``**——否则 GUI 里存完
API key，LLM ``_build_client`` 仍读的是进程启动时 load_dotenv 进来的旧值
（None），表现为"配置页存了 key，运行页还是 NO KEY、点开始没反应 / 跑起来报
LLM_API_KEY is not set"，必须重启 App 才生效（2026-06-08 用户实测）。这些读
env 的地方全是 call-time ``os.getenv``，所以保存时一并更新 ``os.environ``
就能即时生效，无需重启。

**LLM 端点配置（LLM_BASE_URL / LLM_API_KEY / LLM_MODEL）不在 KNOWN_KEYS**：
它们由 Config 顶部的端点选择器（``gui.llm_config``）统一管理（选预设 / 自定义
+ 填 key），不渲染成通用裸框。但 env key 本身仍要可写，所以下面的
``_ALLOWED_KEYS`` 把它们并进来。

API key 字段在前端 mask（password input），后端不主动 mask——前端拿到
真实值后用户改的时候不至于看到 ``***``。
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values, set_key, unset_key

from boss_zhipin.providers import (
    LLM_API_KEY_ENV,
    LLM_BASE_URL_ENV,
    LLM_MODEL_ENV,
)

# 暴露给前端通用表单的字段。每一项映射 ``.env`` 里一个 key。
# 顺序决定前端表单顺序。LLM 端点三件套（base_url/key/model）不在这里——
# 由 Config 顶部的端点选择器（gui.llm_config）管，见 module docstring。
KNOWN_KEYS: list[tuple[str, str, bool]] = [
    # (env key, 字段说明, is_secret)
    ("BOSS_USR_NAME", "你的名字（招呼语署名）", False),
    ("BOSS_LABEL", "求职 tag（空走 BOSS 推荐 feed）", False),
    # RESUME_PATH 不在此处：改由「运行」tab 拖拽上传管理（gui.resume_io），
    # 避免 Config 页一个裸路径输入框成为第二真相源。env 变量本身仍处处生效。
    ("BOSS_CHROME_PROFILE", "Chrome profile 目录（默认 ./chrome_profile）", False),
    ("BOSS_MIN_MATCH_SCORE", "LLM 匹配分阈值（默认 50）", False),
    ("BOSS_EXCLUDE_KEYWORDS", "岗位黑名单（用逗号分隔，如：外包,驻场）", False),
    ("LOGLEVEL", "日志级别（默认 INFO）", False),
]


def _env_path() -> Path:
    return Path(".env")


# 写白名单 = 通用表单字段 ∪ LLM 端点三件套。后者不渲染成通用框，但要能写，
# 所以并进来。其余任何 key 一律拒写（防注入）。
_ALLOWED_KEYS: frozenset[str] = (
    frozenset(k for k, _, _ in KNOWN_KEYS)
    | {LLM_API_KEY_ENV, LLM_BASE_URL_ENV, LLM_MODEL_ENV}
)


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
    return {k: v for k, v in raw.items() if v is not None and k in _ALLOWED_KEYS}


def write_env(updates: dict[str, str]) -> None:
    """把表单提交的 key/value 写回 .env。

    - 空字符串 → ``unset_key`` 把那一行删掉（区别于"留空但保留 key"），
      同时从 ``os.environ`` 里 pop 掉
    - 不存在的 key 自动 append
    - 非空值写文件 + 同步 ``os.environ``，让同进程的 call-time ``os.getenv``
      立即读到新值（无需重启 App，见 module docstring）
    - 跟 read_env 一样**只允许 KNOWN_KEYS 里的字段**，防注入
    """
    path = _env_path()
    path.touch(exist_ok=True)
    for k, v in updates.items():
        if k not in _ALLOWED_KEYS:
            continue
        if v == "":
            try:
                unset_key(str(path), k)
            except Exception:
                pass
            os.environ.pop(k, None)
        else:
            set_key(str(path), k, v, quote_mode="never")
            os.environ[k] = v


def field_meta() -> list[dict[str, str | bool]]:
    """给前端的 fields metadata（key / label / is_secret）。"""
    return [{"key": k, "label": label, "isSecret": is_secret}
            for k, label, is_secret in KNOWN_KEYS]
