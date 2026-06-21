"""LLM provider 的轻量元数据模块。

**为什么单独抽这个模块**：
原本 ``PROVIDER_ENV_KEYS`` / ``detect_providers`` 住在 ``boss_zhipin.cli``，
``cli`` 在 top-level import nodriver / openai / vectorization
（→ sentence_transformers → torch），import 一次 3-10 秒。

PyTauri 的 ``detect_providers`` 命令只需要这两个轻东西，从 ``cli`` import
会把整个重链拖进来 → 阻塞 portal 的 asyncio loop → Config 页 IPC 排队
→ 看上去"一直 loading"。

抽到这里之后，``boss_zhipin.providers`` 只依赖 ``os``，import 是 O(1)。
``cli`` re-export 以兼容旧调用方。
"""
from __future__ import annotations

import os

# provider 名 → 对应在 .env 里读哪个 API key 字段
PROVIDER_ENV_KEYS: dict[str, str] = {
    "deepseek": "DEEPSEEK_API_KEY",
    "chatgpt": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}

# provider 名 → 注册申请 API key 的官方页面（CLI 报错时给用户参考）
PROVIDER_SIGNUP: dict[str, str] = {
    "deepseek": "https://platform.deepseek.com/api_keys",
    "chatgpt": "https://platform.openai.com/api-keys",
    "claude": "https://console.anthropic.com/settings/keys",
}

# provider 名 → 给用户看的显示名（GUI 服务商选择器用）。内部名 chatgpt/claude
# 是历史 CLI 参数，对用户没意义，展示层统一成大家认识的品牌名。
PROVIDER_LABELS: dict[str, str] = {
    "deepseek": "DeepSeek",
    "chatgpt": "OpenAI",
    "claude": "Anthropic · Claude",
}


def detect_providers() -> list[str]:
    """返回当前 env 里配了 API key 的 provider 名字列表。"""
    return [name for name, env in PROVIDER_ENV_KEYS.items() if os.getenv(env)]
