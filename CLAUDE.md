# CLAUDE.md

给 AI 协作者（Claude Code / Cursor / Copilot）的项目背景说明。读完这一份再动代码。

## 项目是干嘛的

一个 BOSS 直聘自动打招呼脚本：

1. 用 `nodriver` 起一个 Chrome（独立 profile，不动用户日常浏览器）。
2. 登录 BOSS（第一次扫码，cookie 落地 `chrome_profile/` 之后跳过）。
3. 在推荐 feed 里挨个抓岗位 JD。
4. 把 JD + RAG 召回的简历片段塞进 prompt，调 LLM 生成中文招呼语。
5. 校验招呼语（长度、CJK、黑名单），通过就点"立即沟通"发送，否则只写日志。

**重点**：这是一个**个人求职辅助工具**，不是高频爬虫，不是绕过反爬的研究项目。
不要写任何"提高发送频率"、"绕过 BOSS 检测的更激进策略"之类的改动。

## 红线

### 不要做的事
- **不要把 Claude / Copilot 写进 commit 的 `Co-Authored-By` trailer**。
  仓库 owner 偏好 commit history 是人的署名。
- **不要写"提速 / 并发 / 绕反爬"的改动**。BOSS 上的反爬越激进，对真实求职者
  伤害越大；这个脚本不希望成为推手。
- **不要 mock 浏览器自动化和真 LLM 做"端到端测试"**。这样测出来的东西在生产
  里 100% 不能用。`finding_jobs.py` 的验证靠手动 `DRY_RUN`，不靠单测。
- **不要 commit 敏感产物**：`.env` / `assistant.json` / `chrome_profile/` /
  `vectorstores/` / `logs/` / `resume/*.pdf`。所有这些都在 `.gitignore`，CI
  里有 `no-leak` job 兜底检查。
- **不要主动去改 `.gitignore` 把上述任何一个移出来**。

### 必须做的事
- 改动的模块如果有对应单测（`tests/test_X.py`），**改完先把测试跑过**。
- 新增公开函数加单测，覆盖至少 happy-path + 1 个 edge case。
- 浏览器自动化代码改完务必本地 `DRY_RUN=1 uv run main.py` 跑一遍，确认能进
  letter 生成那一步。
- 中文注释 OK，但是变量名 / 函数名 **必须用英文**。

## 项目结构

```
.
├── main.py                       # 兼容 shim，委托 boss_zhipin.cli（uv run main.py 仍可用）
├── src/boss_zhipin/              # 业务代码都在这个可安装 package 里（src/ 布局）
│   ├── cli.py                    # CLI 入口，env 校验（run_provider 是 CLI/GUI 共用的主循环入口）
│   ├── providers.py              # 轻量元数据：LLM_PRESETS（常用端点快捷）+ is_llm_configured
│   ├── audit/
│   │   ├── __init__.py           # validate_letter / log_attempt（招呼语审核）
│   │   └── telemetry.py          # LLM 调用 telemetry（成本/时长/token 落盘）
│   ├── models/
│   │   ├── llm.py                # 通用 OpenAI 兼容端点 client + RAG 招呼语生成
│   │   └── prompts.py            # 招呼语 prompt 模板
│   ├── utils/
│   │   └── retry.py              # 指数退避重试装饰器
│   ├── vectorization.py          # 简历 PDF → chroma 向量化 + 召回
│   ├── website_oper/
│   │   ├── finding_jobs.py       # nodriver 浏览器自动化
│   │   └── write_response.py     # 主循环：JD → LLM → 校验 → 发送/日志
│   ├── gui/                      # 桌面 App 胶水层（events/runner/log_bridge/env_io/history）
│   └── tauri/                    # PyTauri 桌面 App（python -m boss_zhipin.tauri）
├── tests/                        # pytest 单测，每个核心模块对应一个 test_X.py
├── docs/wiki/                    # 中文 wiki + ADR
├── .github/workflows/ci.yml      # GitHub Actions
└── .env.example                  # env 变量样板
```

## 关键设计决策（先读这些再改）

### nodriver 而不是 Selenium / undetected-chromedriver
- `undetected-chromedriver` 已停止维护（最新版 2024-02，跟 Chrome 147 协议对不齐）
- Selenium 抗不住 BOSS 的反爬
- `nodriver` 由 uc 原作者维护，CDP 直连，无 chromedriver 中间层
- 详见 [`docs/wiki/adr/001-nodriver-over-selenium.md`](docs/wiki/adr/001-nodriver-over-selenium.md)

### 通用 OpenAI 兼容端点（不分 provider）
- 只 import `openai`，统一一个端点 = `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL`
- DeepSeek / OpenAI / Claude / 百炼·通义千问 / 智谱GLM / 豆包 / Kimi / 本地 Ollama /
  任意中转都走同一条路，代码**不认牌子**。GUI 用 `providers.LLM_PRESETS` 做"常用快捷"
  自动填 base_url + model，但那只是便利，不是支持范围的限制
- `llm._build_client()` 无参，call-time 读 `LLM_*`；`generate_letter` 不再收 provider 名
- 2026-06 重构：移除了具名 provider 路由 + OpenAI Assistants 分支（`openai_assistant.py`
  已删），详见 [`docs/wiki/adr/002-three-providers.md`](docs/wiki/adr/002-three-providers.md) 顶部更新

### sync facade + async impl
- `finding_jobs.py` 对外是同步 API（`open_browser_with_options` / `log_in` /
  `select_dropdown_option` ...），内部用 `nodriver` 的 async API + 共享的
  `uc.loop().run_until_complete()` 桥接
- 这样 `write_response.py` 和 `main.py` 不需要全部改成 async
- 改动这一层时小心别破坏 async/sync 边界

### `validate_letter` 是必经之路
- 任何 LLM 生成的招呼语**都要先过 `audit.validate_letter`** 再发送
- 拦截规则：长度区间 / 必须含中文 / 黑名单（"Error" / "As an AI" / "```" ...）
- 不要改这个逻辑去"放宽校验"，规则严是有原因的（防止把 LLM 抽风的输出发给真招聘者）

### 持久化 profile 是登录态的核心
- `./chrome_profile/` 是独立 Chrome profile，第一次扫码后 cookie 留下
- **不要在 PR 里改这个目录的命名 / 默认位置**，已经有用户依赖
- 用户可以用 `BOSS_CHROME_PROFILE` env 覆盖

## 测试 / CI 套件

- 跑测试：`uv run pytest tests/ -v`
- Smoke import check（参见 `.github/workflows/ci.yml`）会硬 import 每个核心模块，
  改名 / 移文件后要同步更新里面那一串 `uv run python -c "import ..."`
- 添加新模块时记得在 ci.yml 那里加一行
- CI 里 `BOSS_RETRY_BASE_DELAY=0.01` 加速 retry 测试，本地跑测试如果觉得慢可以
  `export BOSS_RETRY_BASE_DELAY=0.01`

## 跟人对齐的途径

- 大改动（重构 / 加新 provider / UI）：**先开 issue 讨论**，不要直接发 PR
- 小改动（修字 / 加测试 / 修 bug）：直接 PR
- 不确定算大还是小：先开 issue 简短描述，等一个 thumbs up 再动手

## 如果你是 AI 在读这个

记住：你不是 maintainer。你是协作者。每次大改动前问自己：

1. 这个改动是 maintainer 明确要求的，还是我自己脑补出来的"显然应该改"？
2. 改完测试还过吗？
3. 我有没有把不该 import 的模块（比如把 audit/letters.jsonl 的格式改了）牵连进去？
4. 我有没有把"Claude" 写进 commit message？（**不要**）

谨慎一点。
