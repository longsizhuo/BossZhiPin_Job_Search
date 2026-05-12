# 架构总览

## 一句话

读 BOSS 推荐 feed → 抓 JD → 给 LLM 生成中文招呼语 → 校验后发送 →
所有动作落盘审计。

## 数据流

```
                        ┌─────────────────────┐
                        │      main.py        │
                        │ env / provider 路由 │
                        └──────────┬──────────┘
                                   │
                                   ▼
                ┌──────────────────────────────────────┐
                │  send_job_descriptions_to_chat       │
                │  ([write_response.py])               │
                └─────┬──────────────┬──────────┬──────┘
                      │              │          │
        ┌─────────────┘              │          └──────────────┐
        ▼                            ▼                         ▼
┌──────────────┐          ┌──────────────────┐        ┌─────────────────┐
│ finding_jobs │          │   LLM provider   │        │  audit + log    │
│  (nodriver)  │          │ (deepseek/chat-  │        │                 │
│              │          │  gpt/claude)     │        │ validate_letter │
│ - open       │          │                  │        │ log_attempt     │
│ - log_in     │          │ models/llm.py    │        │ record_llm_call │
│ - JD by idx  │          │ write_response   │        └─────────────────┘
│ - click_xpath│          │   .chat()        │
│ - send msg   │          │                  │
└──────────────┘          └──────────────────┘
        │                          │
        ▼                          ▼
  ┌──────────┐             ┌────────────────┐
  │ Chrome   │             │ OpenAI / Deep- │
  │ (CDP)    │             │ seek / Claude  │
  │ profile  │             │ API endpoint   │
  └──────────┘             └────────────────┘
                                   │
                                   ▼
                        ┌────────────────────┐
                        │ vectorization.py   │
                        │ (chroma + sentence │
                        │  -transformers)    │
                        │                    │
                        │ 召回 top-4 简历切片 │
                        └────────────────────┘
```

## 模块边界

| 模块 | 职责 | 不该做的事 |
|---|---|---|
| `main.py` | 启动时校验 env、走 prompt 让用户输入缺的、按 provider 分发 | 调浏览器 / 调 LLM |
| `audit/__init__.py` | 招呼语校验（长度/CJK/黑名单）+ 业务审计 JSONL | 调 LLM / 调浏览器 |
| `audit/telemetry.py` | LLM 调用 telemetry JSONL（成本/时长/token） | 业务校验 |
| `models/llm.py` | DeepSeek / Claude / OpenAI 的统一 chat completions 入口 | 浏览器操作 |
| `models/openai_assistant.py` | OpenAI Assistants API（需要 vector store） | 直接调 chat completions |
| `utils/retry.py` | 通用指数退避装饰器 | 知道任何业务 |
| `vectorization.py` | 简历 PDF 解析 + chroma 向量化 + 召回 | 调 LLM |
| `website_oper/finding_jobs.py` | nodriver 浏览器自动化（sync facade + async impl） | 业务逻辑（生成招呼语等） |
| `website_oper/write_response.py` | 主循环：JD → LLM → 校验 → 发送/日志 | 直接操作 DOM（应该走 finding_jobs 的 helper） |

## 关键抽象

### `VectorStore`（[vectorization.py](../../vectorization.py)）
对 chroma collection 的薄封装，对外只一个方法 `.search(query, k)`。第一次跑会
按简历 PDF 的 MD5 建一个独立的持久化目录 `vectorstores/<md5>/`，之后跑同样的
PDF 就直接 reload，不需要重新 embedding。

### `PROVIDERS`（[models/llm.py](../../models/llm.py)）
三家 LLM provider 的配置注册表。增删 provider 只需要改这一个 dict，加 1 行。
利用所有家都提供 OpenAI 兼容端点这一事实，省掉了 anthropic-sdk 等额外依赖。

### sync facade + async impl（[finding_jobs.py](../../website_oper/finding_jobs.py)）
nodriver 只有 async API，但项目里 `main.py` 和 `write_response.py` 是 sync 流程。
模式：
- 每个 public 函数是 sync 的，比如 `open_browser_with_options(url, browser)`。
- 它的实现叫 `_open_browser_impl(url)`，是 async 的。
- public 函数里 `_run(coro)` 内部就一行：
  `return uc.loop().run_until_complete(coro)`。

这样 caller 不需要 import asyncio，但内部仍然享有 nodriver 的 async benefits。

### `validate_letter` 必经之路（[audit/__init__.py](../../audit/__init__.py)）
任何 LLM 输出在被发到 BOSS 之前**必须**过 `validate_letter`：

- 长度区间（默认 30~800 字符）
- 必须含至少一个 CJK 字符（防止 LLM 误用英文回复）
- 黑名单（"Error" / "Traceback" / "As an AI" / `\`\`\`` 等表示 LLM 抽风的字符串）

失败的招呼语**绝对不发送**，但会照样写一行到 `logs/letters.jsonl`，方便事后调
prompt。

## 三种 provider 路径对比

| 维度 | DeepSeek | OpenAI Assistants | Claude |
|---|---|---|---|
| 入口函数 | `generate_letter` | `chat`（在 write_response.py） | `generate_letter` |
| RAG 实现 | 本地 chroma + sentence-transformers 召回 | OpenAI Vector Store（远端） | 同 DeepSeek |
| 单次调用成本 | 最便宜 | 中 | 偏贵 |
| 首次跑下载量 | ~430 MB（embedding 模型） | 0 | ~430 MB |
| 适用场景 | 量大、对成本敏感 | 想要 OpenAI 一站式 | 在意中文语感、能负担成本 |

## 业务循环主流程

`send_job_descriptions_to_chat` 是 `main.py` 路由进来的总入口。简化后的伪代码：

```python
finding_jobs.open_browser_with_options(url, "chrome")
finding_jobs.log_in()

select_dropdown_option(label)  # 可选过滤
job_index = 1
consecutive_misses = 0

while True:
    jd = finding_jobs.get_job_description_by_index(job_index)
    if jd is None:
        consecutive_misses += 1
        if consecutive_misses >= 5:
            break  # 列表底部
        continue

    chat_btn_text = finding_jobs.get_text_by_css(".op-btn.op-btn-chat")
    if chat_btn_text != "立即沟通":
        job_index += 1; continue

    letter = generate_letter(...) or chat(...)
    validation = validate_letter(letter)

    if not validation.ok:
        log_attempt(sent=False)
    elif dry_run:
        log_attempt(dry_run=True, sent=False)
    else:
        finding_jobs.click_by_xpath(contact_button_xpath)
        finding_jobs.send_chat_message(letter)
        log_attempt(sent=True)

    job_index += 1
```

## 落盘文件清单

| 文件 | 内容 | 谁写 |
|---|---|---|
| `logs/letters.jsonl` | 每条招呼语的 audit（含 JD + 招呼语 + 是否发送） | `audit.log_attempt` |
| `logs/llm_calls.jsonl` | 每次 LLM 调用的 telemetry（成本 / 延迟 / token） | `audit.telemetry.record_llm_call` |
| `vectorstores/<md5>/` | 简历向量化结果（chroma 持久化目录） | `vectorization.embed_pdf` |
| `chrome_profile/` | 独立 Chrome profile，含登录 cookie | `nodriver`（间接） |
| `assistant.json` | OpenAI Assistant ID 缓存 | `models.openai_assistant.create_assistant` |

全部在 `.gitignore` 里，不会进版本控制。

## 为什么这么设计

详见 ADR 文档：

- [ADR-001](adr/001-nodriver-over-selenium.md) —— 浏览器自动化选型
- [ADR-002](adr/002-three-providers.md) —— provider 设计
- [ADR-003](adr/003-telemetry-separate.md) —— 为什么 telemetry 不并进 letters audit
- [ADR-004](adr/004-persistent-chrome-profile.md) —— 持久化 profile 决策
