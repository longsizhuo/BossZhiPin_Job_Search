# ADR-002：三家 LLM provider 共用 OpenAI SDK，按 `base_url` 切换

- **状态**：已采纳
- **日期**：2026-05-10
- **决策人**：longsizhuo
- **相关 commit**：[`e83e314`](https://github.com/longsizhuo/BossZhiPin_Job_Search/commit/e83e314)
  (引入多 provider) + [`ffbab2f`](https://github.com/longsizhuo/BossZhiPin_Job_Search/commit/ffbab2f)
  (OPENAI_BASE_URL 接通)

## 背景

项目原版只支持 OpenAI。中文用户场景里 OpenAI 价格 + 访问门槛都偏高，社区希望
加 DeepSeek / Claude / 国产 LLM。

直觉的做法是引入 `anthropic-sdk-python`、`deepseek-sdk`、`zhipuai` 等各家
SDK。但这意味着：

- 依赖体积扩大（每家 SDK 通常 10MB+）
- 三套相似但不一致的 chat completions 接口要维护
- 每家 SDK 的 retry / timeout / streaming 语义略有不同

## 关键洞察

**DeepSeek 和 Anthropic Claude 都提供 OpenAI 兼容端点**：

- DeepSeek：`https://api.deepseek.com`
- Anthropic：`https://api.anthropic.com/v1/`

只要 `openai.OpenAI(api_key=..., base_url=...)` 改一下 base_url，三家共用一份
代码。

## 决策

只 import `openai` 一家 SDK。三家 provider 在 [`models/llm.py`](../../models/llm.py)
的 `PROVIDERS` 字典里登记 base_url 和 api_key 环境变量：

```python
PROVIDERS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
    },
    "claude": {
        "base_url": "https://api.anthropic.com/v1/",
        "api_key_env": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-6",
    },
    "openai": {
        "base_url": None,    # 用 SDK 默认
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
    },
}
```

`_build_client(provider)` 根据 provider 名构造 client + 默认 model。
`generate_letter` 走统一的 `client.chat.completions.create(...)`。

## 例外：OpenAI Assistants API

OpenAI 自己有 **Assistants API**（管理对话 thread + 绑定 vector store），
**不是**所有家都有的。它仍然走 openai SDK，但调用入口不同（`client.beta.assistants.*`、
`client.beta.threads.*`、`client.vector_stores.*`），代码在
[`models/openai_assistant.py`](../../models/openai_assistant.py) 单独一份。

这意味着 "chatgpt" provider 跟 "deepseek" / "claude" 用的不是同一条代码路径：

- DeepSeek / Claude → `generate_letter`（本地 RAG）
- OpenAI Assistants → `chat` in `write_response.py`（远端 vector store + thread run）

## 代价 / 限制

1. **OpenAI 那边 sometimes 修改 chat completions 协议**（比如 `tool_calls` 字段
   schema 微调），DeepSeek / Claude 可能慢一步跟进。我们手测时发现过 Claude
   的 OpenAI 兼容端点偶尔不支持 `temperature=0`，但 0.4 没问题。
2. **streaming**：三家 streaming 实现细节稍有不同，目前我们不开 streaming，
   所以不踩坑。如果要加 streaming，会需要 per-provider 测试。
3. **token 统计**：三家都在 response.usage 里返回 prompt_tokens /
   completion_tokens，schema 一致。但 OpenAI Assistants 走 run 对象，字段名
   完全不同（`prompt_tokens` / `completion_tokens` 同名但挂在 `run.usage`）。
   `audit.telemetry._telemetry_for_run` 单独处理。

## 备选方案

### A. 每家用各自原生 SDK
- ❌ 依赖膨胀
- ❌ 三份相似代码

### B. 用 LiteLLM 统一封装
- ⚠️ 多一层抽象，本质上做的事跟我们直接用 `base_url` 切换一样
- ❌ 多一个外部维护方，多一个版本对齐压力
- ❌ LiteLLM 升级偶尔会引入 breaking change

### C. 现在的方案（采纳）
- ✅ 一个 SDK，三份配置
- ✅ 加新 provider 只需 4 行（PROVIDERS 字典里加一条 + .env.example 加注释 +
  pricing 表加一行）
- ✅ 因为所有家共享 `openai.OpenAI` API surface，单测里能用统一的 mock

## 验证

实际跑过：

- ✅ DeepSeek `deepseek-chat`：~¥0.002/次，~1.5s 延迟
- ✅ Claude `claude-sonnet-4-6`：~¥0.04/次，~2-3s 延迟
- ✅ OpenAI `gpt-4o` Assistants：~¥0.02/次，~3-5s 延迟（thread run 多了一跳）

## 后续

加新 provider 时检查清单：

- [ ] 它有 OpenAI 兼容端点吗？没有的话考虑是否值得开 SDK 例外
- [ ] [`src/boss_zhipin/models/llm.py`](../../src/boss_zhipin/models/llm.py) `PROVIDERS` 加一条
- [ ] [`src/boss_zhipin/cli.py`](../../src/boss_zhipin/cli.py) `PROVIDER_ENV_KEYS` + `PROVIDER_SIGNUP` 加一条
- [ ] [`.env.example`](../../.env.example) 加注释 + 申请链接
- [ ] [`src/boss_zhipin/audit/telemetry.py`](../../src/boss_zhipin/audit/telemetry.py) `PRICING_CNY_PER_M_TOKENS` 加一行
- [ ] [`tests/test_main_helpers.py`](../../tests/test_main_helpers.py)
  里加一个 detect_providers 覆盖
- [ ] 跑一次 `DRY_RUN=1` 看实际效果
