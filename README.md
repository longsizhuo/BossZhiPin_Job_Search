# BOSS 直聘自动打招呼脚本

> **🤖 If You are AI agents **：当用户问"怎么装这个项目"、"`uv` 命令找不到"、"扫码扫不上"、"`DEEPSEEK_API_KEY` 怎么填"之类的小白问题时，**请直接加载并使用本仓库的 [`boss-zhipin-onboarding`](.claude/skills/boss-zhipin-onboarding/) skill**。它自带 5 步里程碑流程、`scripts/check-env.sh` 一键诊断脚本，以及面向零基础用户的沟通规范，比你从这份 README 重新组织一遍引导更可靠。
[中文](README.md) · [English](README_EN.md)

读 BOSS 上的岗位描述，用 LLM 给 HR 生成一封礼貌的打招呼语，按规则审核后再发送。支持 DeepSeek / OpenAI / Claude 三个 provider，任意一个 key 都能起跑。

> 原作者已经暂停维护，目前由我和小伙伴们继续优化。已完成迁移到 [uv](https://docs.astral.sh/uv/) 管理依赖、移除 langchain 全家桶、把浏览器自动化从 Selenium 迁到 [nodriver](https://github.com/ultrafunkamsterdam/nodriver)（绕过 BOSS 反爬更稳）。

> ⚠️ 请勿用本脚本割韭菜。能被逼到用脚本投简历的人，身上没啥油水可榨。

---

## 免责声明

- 本项目是**免费、开源**的个人求职辅助工具，按 [MIT 许可证](LICENSE) 提供，**不收费、不接受打赏、不做任何商业化**。
- 使用浏览器自动化访问 BOSS 直聘**可能违反其服务条款**。是否使用、如何使用，以及由此产生的任何后果（账号风险、法律风险等），**均由使用者自行承担**。
- 本软件按「现状」（AS IS）提供，**不附带任何形式的担保**。作者与贡献者不对使用本软件造成的任何损失或纠纷负责。
- 请仅将本工具用于**个人求职**用途，发送前自行审阅生成的招呼语；请勿用于高频群发、骚扰或任何损害他人的目的。

---

## 快速开始（5 分钟）

### 前置

- Python >= 3.11
- macOS / Linux / Windows（脚本目前只支持 Chrome / Chromium，nodriver 不支持 Edge/Safari）
- 装好 Chrome（不是 Chromium beta，普通 stable 即可）
- 装好 [uv](https://docs.astral.sh/uv/)：`curl -LsSf https://astral.sh/uv/install.sh | sh`

### 跑起来

```bash
# 1. clone + 安装依赖
git clone https://github.com/longsizhuo/BossZhiPin_Job_Search.git
cd BossZhiPin_Job_Search
uv sync

# 2. 配 API key
cp .env.example .env
# 编辑 .env，至少填一个 LLM provider 的 key（详见下方 .env 字段说明）

# 3. 准备简历
mkdir -p resume
# 把你的 PDF 简历复制进去，命名 my_cover.pdf
# 或者在 .env 设 RESUME_PATH 指向别的位置

# 4. dry-run 试一下（只生成、不发送）
DRY_RUN=1 uv run main.py

# 5. 确认 logs/letters.jsonl 里的招呼语质量 OK，再去掉 DRY_RUN 真跑
uv run main.py
```

### 首次运行：扫码登录

脚本会用 `./chrome_profile/` 这个独立目录起 Chrome（**不会动你日常浏览器**）。第一次会被 BOSS 重定向到登录页，自动点上"微信扫码"，你扫一次码登录成功后 cookie 留在 `chrome_profile/`，**后续运行都跳过登录**。

---

## 桌面 App（GUI）

两种跑法（设计细节见 [ADR-005](docs/wiki/adr/005-pytauri-standalone.md)）：

```bash
# 开发模式：Python 主进程 + pytauri-wheel（uv sync 默认就装 tauri 组）
uv sync
uv run python -m boss_zhipin.tauri

# 不想装桌面 App 那一坨（纯 CLI 用户）：
# uv sync --no-group tauri

# Standalone .app（macOS）：打一个双击就能跑的 bundle
./scripts/build_standalone.sh
# 产物在 src-tauri/target/bundle-release/bundle/macos/
```

Standalone 模式的用户数据（`.env` / `chrome_profile/` / `logs/` /
`vectorstores/`）落在 `~/Library/Application Support/com.longsizhuo.boss-zhipin/`，
跟 repo 目录互不干扰。

---

## `.env` 字段速查

仓库根目录的 [`.env.example`](.env.example) 是完整模板，几个关键字段：

| 字段 | 作用 | 必填 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek key（[申请](https://platform.deepseek.com/api_keys)） | 三选一 |
| `OPENAI_API_KEY` | OpenAI key，用于 Assistants 模式（[申请](https://platform.openai.com/api-keys)） | 三选一 |
| `ANTHROPIC_API_KEY` | Anthropic Claude key（[申请](https://console.anthropic.com/settings/keys)） | 三选一 |
| `BOSS_USR_NAME` | 你的名字，会出现在招呼语署名里 | 否（不填会启动时问你） |
| `BOSS_LABEL` | 求职 tag，比如"后端开发（成都）" | 否（不填就用 BOSS 默认推荐 feed） |
| `RESUME_PATH` | 简历 PDF 路径 | 否（默认 `./resume/my_cover.pdf`） |
| `DRY_RUN` | `1` = 只生成不发送 | 否 |
| `BOSS_MIN_MATCH_SCORE` | LLM 匹配分阈值 | 否（默认 50） |
| `BOSS_EXCLUDE_KEYWORDS` | 岗位黑名单关键字（用逗号分隔，如"外包,驻场"） | 否 |
| `LOGLEVEL` | 日志级别 | 否（默认 INFO） |

**只配一个 key 时脚本会自动选用，不会让你选**；配多个时启动时让你选；一个都不配会列出 signup 链接然后退出。

---

## 三种 provider 怎么选

| Provider | 路径 | 优势 | 劣势 |
|---|---|---|---|
| DeepSeek | RAG 模式（自建 chroma 向量库 + sentence-transformers 召回简历片段） | 最便宜，质量过得去 | 首次跑会下载 embedding 模型 (~430MB) |
| OpenAI | Assistants API + Vector Stores（OpenAI 那边管简历向量化） | 不用本地 embedding，省内存 | 每次调用比 DeepSeek 贵不少 |
| Claude | RAG 模式（同 DeepSeek） | 招呼语风格更自然 | 模型本身贵，但走 RAG 单次 token 少 |

---

## 安全：dry-run + 审计日志

每封生成的招呼语在发送前都会过 [`audit.py`](audit.py) 里的 `validate_letter`：
- 长度区间检查（默认 30~800 字符）
- 必须包含中文字符
- 黑名单关键词（"Error"、"Traceback"、"As an AI"、"```" 等），命中即拦截

无论是发送成功、被拦截还是 dry-run，都会追加一行 JSONL 到 `./logs/letters.jsonl`，包括 JD、生成内容、provider、model、validation 结果。复盘事故 / 调 prompt 用得着：

```bash
tail -f logs/letters.jsonl | jq '{ts, sent, validation_ok, validation_reasons, letter_len}'
```

---

## Troubleshooting

### 浏览器闪退 / 起不来 / `SessionNotCreatedException`
旧版本用过 `undetected-chromedriver`，它自带的 chromedriver 跟 Chrome 版本对不齐就崩。本仓库已迁到 [nodriver](https://github.com/ultrafunkamsterdam/nodriver)，**没有 chromedriver**，直接走 CDP，所以这类版本错误结构上不会发生。如果还是闪退，多半是 profile 被锁。

### Chrome 启动后 profile 显示空白 / "好像不是我的 Chrome"
对，脚本默认用 **独立 profile**（`./chrome_profile/`），不是你日常 Chrome。这是设计——避免影响你日常浏览器的扩展和登录状态。第一次会让你扫码登录 BOSS，之后 cookie 留在这个独立 profile 里。

想用日常 Chrome 的 cookie？把日常 Chrome 完全退出，然后：
```bash
BOSS_CHROME_PROFILE="$HOME/Library/Application Support/Google/Chrome" uv run main.py
```
**警告**：日常 Chrome 必须先完全关掉（菜单栏 → Quit Google Chrome），不然 profile 会被锁。

### 弹出 newtab、看不到 BOSS 页面
旧 profile 里有恢复 tab 时会发生。新版本 ([commit `7dbdf37`](https://github.com/longsizhuo/BossZhiPin_Job_Search/commit/7dbdf37)) 起来直接在新窗口里打开 BOSS，已经修了。

### 卡在 "页面已稳定" 之后不动
应该没了——之前是 `tab.select(timeout=0)` 在 nodriver 里阻塞。如果还遇到，把控制台输出贴 issue 里。

### 提示"❌ 找不到简历文件"
按提示把 PDF 放到 `./resume/my_cover.pdf`，或者 `.env` 里 `RESUME_PATH=...`。

### 提示"❌ 没找到任何 API key"
按提示去申请一个填到 `.env`。最少只需要一个。

---

## 项目结构

```
.
├── main.py                       # 兼容 shim：uv run main.py 仍然可用，实际委托 boss_zhipin.cli
├── src/boss_zhipin/              # 业务代码都在这个可安装 package 里
│   ├── cli.py                    # CLI 入口，处理交互/env 校验/路由 provider
│   ├── models/
│   │   ├── llm.py                # provider 配置 + DeepSeek/Claude 的 chat completions 调用
│   │   ├── openai_assistant.py   # OpenAI Assistants 模式（带 vector store 的）
│   │   └── prompts.py            # 招呼语 prompt 模板
│   ├── website_oper/
│   │   ├── finding_jobs.py       # 浏览器自动化（nodriver），sync facade + async impl
│   │   └── write_response.py     # 单个岗位的主循环：JD → 生成 → 校验 → 发送/日志
│   ├── vectorization.py          # 简历 PDF 解析 + sentence-transformers 向量化 + Chroma 持久化
│   ├── audit/                    # 招呼语校验 + JSONL 审计日志 + LLM telemetry
│   ├── gui/                      # 桌面 App 的胶水层（不依赖 PyTauri 本身）
│   └── tauri/                    # PyTauri 桌面 App 入口（uv run python -m boss_zhipin.tauri）
└── .env.example                  # 所有环境变量的注释样板
```

---

## 想加入维护？

我们寻求更多小伙伴加入。如果你愿意做：
- Electron 前端 UI
- 给 BOSS 发简历附件
- 投递历史 / 自动跟进
- 多账号支持

发 issue 或者 PR 都行。

---

## 致谢

感谢所有支持本项目的人：

<p align="left">
    <a href="https://github.com/longsizhuo/BossZhiPin_Job_Search/graphs/contributors">
        <img width="770" src="https://contrib.rocks/image?repo=longsizhuo/BossZhiPin_Job_Search&max=300&columns=16" />
    </a>
</p>

### 衍生项目

- [noBaldAaa/find-job](https://github.com/noBaldAaa/find-job) — 基于 JS 的更简版本
- [LouisCaixuran/auto_job_find_azure](https://github.com/LouisCaixuran/auto_job_find_azure) — 基于 Azure OpenAI 的版本
