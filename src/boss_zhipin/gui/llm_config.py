"""GUI Config 的 LLM 端点配置——通用 OpenAI 兼容端点 (base_url + key + model)。

不分 provider：存进 .env 的就是 ``LLM_BASE_URL`` / ``LLM_API_KEY`` / ``LLM_MODEL``
三个键。``LLM_PRESETS`` 只是给前端一个"选了自动填 base_url + model"的快捷列表，
**不是支持范围的限制**——填任意 base_url + model 就能接任何 OpenAI 兼容端点。

读 .env **文件**为准（GUI standalone 启动时还没 load_dotenv，os.environ 是空的）；
run 路径靠 models 的 import-time load_dotenv 自愈。写走 ``env_io.write_env``：
落盘 + 同步 os.environ（存完即时生效，不用重启）。
"""
from __future__ import annotations

from dotenv import dotenv_values

from boss_zhipin.gui.env_io import _env_path, write_env
from boss_zhipin.providers import LLM_PRESETS


def _file_values() -> dict[str, str | None]:
    path = _env_path()
    return dotenv_values(path) if path.is_file() else {}


def read_llm_config() -> dict[str, object]:
    """返回前端 Config 需要的：当前 base_url / model / 是否已配 key + 预设列表。

    不回传 key 明文（前端只需知道有没有）。前端按 baseUrl 匹配预设来高亮选项，
    匹配不上就是「自定义」。
    """
    raw = _file_values()
    return {
        "baseUrl": (raw.get("LLM_BASE_URL") or "").strip(),
        "model": (raw.get("LLM_MODEL") or "").strip(),
        "hasKey": bool((raw.get("LLM_API_KEY") or "").strip()),
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
