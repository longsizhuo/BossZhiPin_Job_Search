"""LLM 端点的轻量元数据模块。

**为什么单独抽这个模块**：PyTauri 的 Config 命令 / CLI 帮助只需要"预设列表"
和"是否配好了"这两个轻东西，从 ``cli`` import 会把 vectorization →
sentence_transformers → torch（3-10s）整条重链拖进来 → 阻塞 portal loop。
这里只依赖 ``os``，import 是 O(1)。

**配置模型（2026-06 重构）**：不再分 deepseek/chatgpt/claude 三个 provider，
统一成一个 **OpenAI 兼容端点** = ``base_url`` + ``api_key`` + ``model`` 三个
``LLM_*`` 环境变量。三家（以及本地 Ollama / 各种中转）都用 ``openai`` SDK 通过
``base_url`` 改写访问，代码不再"认牌子"。下面的 ``LLM_PRESETS`` 只是给 GUI 一个
"选了自动填好 base_url + model"的便利，选「自定义」可填任意端点。
"""
from __future__ import annotations

import os

# 环境变量名——单一真相源，env_io 白名单 / llm._build_client / llm_config 都引用。
LLM_API_KEY_ENV = "LLM_API_KEY"
LLM_BASE_URL_ENV = "LLM_BASE_URL"
LLM_MODEL_ENV = "LLM_MODEL"

# 预设：选一个就自动填 base_url + model，多数用户只需再粘一个 key。
# **这不是支持范围的限制**——引擎只认 base_url+key+model，任何 OpenAI 兼容端点
# 都能跑（GUI 默认「自定义」可填任意端点）。这里只是给常见平台一个快捷填充，
# 列表不穷举、随时能加。base_url / model 都是可编辑的默认值（model 各家会更新，
# 填错了用户自己改即可）。key 是内部代号，label 给用户看。
LLM_PRESETS: dict[str, dict[str, str]] = {
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "signup_url": "https://platform.deepseek.com/api_keys",
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "signup_url": "https://platform.openai.com/api-keys",
    },
    "claude": {
        "label": "Anthropic · Claude",
        "base_url": "https://api.anthropic.com/v1/",
        "model": "claude-sonnet-4-6",
        "signup_url": "https://console.anthropic.com/settings/keys",
    },
    "qwen": {
        "label": "通义千问 · 阿里云百炼",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "signup_url": "https://bailian.console.aliyun.com/",
    },
    "glm": {
        "label": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-plus",
        "signup_url": "https://open.bigmodel.cn/usercenter/apikeys",
    },
    "doubao": {
        "label": "豆包 · 火山方舟",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-pro-32k",
        "signup_url": "https://console.volcengine.com/ark",
    },
    "kimi": {
        "label": "Kimi · Moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "signup_url": "https://platform.moonshot.cn/console/api-keys",
    },
    "minimax": {
        "label": "MiniMax",
        "base_url": "https://api.minimaxi.com/v1",
        "model": "abab6.5s-chat",
        "signup_url": "https://platform.minimaxi.com/",
    },
    "siliconflow": {
        "label": "硅基流动 SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "deepseek-ai/DeepSeek-V3",
        "signup_url": "https://cloud.siliconflow.cn/account/ak",
    },
    "ollama": {
        "label": "本地 Ollama",
        "base_url": "http://localhost:11434/v1",
        "model": "llama3",
        "signup_url": "https://ollama.com/",
    },
}


def is_llm_configured() -> bool:
    """是否填了 LLM API key（最低可跑条件）。读 ``os.environ``。"""
    return bool(os.getenv(LLM_API_KEY_ENV, "").strip())
