"""GUI Config 的 LLM 端点配置——通用 OpenAI 兼容端点 (base_url + key + model)。

不分 provider：存进 .env 的就是 ``LLM_BASE_URL`` / ``LLM_API_KEY`` / ``LLM_MODEL``
三个键。``LLM_PRESETS`` 只是给前端一个"选了自动填 base_url + model"的快捷列表，
**不是支持范围的限制**——填任意 base_url + model 就能接任何 OpenAI 兼容端点。

真相源 = ``os.environ`` 优先、回退 .env **文件**：GUI standalone 启动时还没
load_dotenv，os.environ 里没有 .env 的值 → 读文件；但若用户在 shell 里
``export LLM_API_KEY=...`` 而 .env 没写，os.environ 有、文件没有 → 也要认账，
否则会和运行时 ``llm._build_client``（读 os.environ）判断打架，把本可跑的配置
误拦成"还没配 AI"。写走 ``env_io.write_env``：落盘 + 同步 os.environ（存完即时
生效，不用重启）。
"""
from __future__ import annotations

import os

from dotenv import dotenv_values

from boss_zhipin.gui.env_io import _env_path, write_env
from boss_zhipin.providers import LLM_PRESETS


def _file_values() -> dict[str, str | None]:
    path = _env_path()
    return dotenv_values(path) if path.is_file() else {}


def _effective(key: str, file_values: dict[str, str | None]) -> str:
    """os.environ 优先、回退 .env 文件，取一个 LLM_* 的有效值。"""
    return (os.environ.get(key) or file_values.get(key) or "").strip()


def read_llm_config() -> dict[str, object]:
    """返回前端 Config 需要的：当前 base_url / model / 是否已配 key + 预设列表。

    不回传 key 明文（前端只需知道有没有）。前端按 baseUrl 匹配预设来高亮选项，
    匹配不上就是「自定义」。值的真相源见 module docstring（os.environ 优先、回退文件）。
    """
    raw = _file_values()
    return {
        "baseUrl": _effective("LLM_BASE_URL", raw),
        "model": _effective("LLM_MODEL", raw),
        "hasKey": bool(_effective("LLM_API_KEY", raw)),
        "presets": [
            {
                "name": name,
                "label": p["label"],
                "baseUrl": p["base_url"],
                "model": p["model"],
                "signupUrl": p["signup_url"],
            }
            for name, p in LLM_PRESETS.items()
        ],
    }


def write_llm_config(base_url: str, model: str, api_key: str | None) -> None:
    """存端点配置。

    - ``base_url`` 空 → 删掉 LLM_BASE_URL（= 用 OpenAI 默认端点）。
    - ``model`` 空 → 删掉 LLM_MODEL（运行时 _build_client 会报错提示填）。
    - ``api_key`` 为 ``None`` / 空 → **不动已存的 key**（换端点不必重输 key）；
      非空 → 写入。
    写经由 env_io.write_env（"" 即删除 + pop os.environ）。
    """
    updates: dict[str, str] = {
        "LLM_BASE_URL": base_url or "",
        "LLM_MODEL": model or "",
    }
    if api_key:
        updates["LLM_API_KEY"] = api_key
    write_env(updates)
