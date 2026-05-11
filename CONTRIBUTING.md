# 贡献指南

欢迎给本项目提 issue / PR。这份文档说清楚怎么帮忙、什么改动会被收、什么改动需要先讨论。

## 怎么帮忙最有用

| 能做什么 | 大概工作量 | 备注 |
|---|---|---|
| 跑一遍 README quick start，把卡住的地方提 issue | 半小时 | **最有价值**，新用户视角看不到的盲点最多 |
| 报具体 bug + 复现步骤 | 几分钟到几小时 | 优先选 `bug` label 的 issue |
| 修文档错别字 / 不准确的描述 | 几分钟 | 直接发 PR 即可 |
| 给某个模块补单测 | 1-2 小时 | `tests/` 目录下选一个还没覆盖的函数 |
| 把硬编码 BOSS 选择器换成更稳的 | 几小时 | 需要本地跑通 dry-run 验证 |
| 加新 provider 支持（如 Kimi / 通义 / ...） | 半天 | 参考 [`models/llm.py`](models/llm.py) 里 PROVIDERS 字典的扩展方式 |
| Electron / Web UI | 一周起步 | 先发 issue 讨论方向，别直接动 |
| 多账号 / 简历附件 / 投递历史持久化 | 一周起步 | 先发 issue 讨论 |

## 工作流

```bash
# 1. fork + clone
git clone https://github.com/<你的用户名>/BossZhiPin_Job_Search.git
cd BossZhiPin_Job_Search

# 2. 装依赖
uv sync

# 3. 起独立分支
git checkout -b fix/some-bug      # bug 修复
git checkout -b feat/new-provider # 新功能
git checkout -b docs/wiki-typo    # 文档

# 4. 写改动
vim ...

# 5. 跑测试
uv run pytest tests/ -v
# 改了浏览器自动化代码的话还要本地 DRY_RUN 跑一遍主流程
DRY_RUN=1 uv run main.py

# 6. push + 开 PR
git push origin <分支名>
gh pr create
```

## 分支命名

- `fix/<简短描述>` —— bug 修复
- `feat/<简短描述>` —— 新功能
- `docs/<简短描述>` —— 文档
- `chore/<简短描述>` —— 杂活（CI / lint / 依赖升级）
- `refactor/<简短描述>` —— 重构（不改外部行为）

## Commit 信息

中英文都行，但要**讲清楚 why 而不是 what**。差的例子：

```
Update finding_jobs.py
Fix bug
```

好的例子：

```
卡在登录页是因为 BOSS 升级了 selector，把绝对 XPath 换成 contains-text

之前用的是 //*[@id='header']/div[1]/div[3]/div/a 这种结构化 XPath，
2026-04 BOSS 改版后 header 嵌套深度变了，断了。换成 PARTIAL_LINK_TEXT 兜底。
```

每个 commit 限定在一件事 —— review 难度跟 diff size 是平方关系，把 5 件事
打成 5 个 commit 比堆一个大 commit 容易看得多。

## PR 描述

模板（不强制，建议跟）：

```markdown
## 解决的问题
（issue 链接 / 一句话描述）

## 怎么改的
（关键设计决策）

## 测试
- [ ] uv run pytest 全过
- [ ] DRY_RUN 跑一遍至少能进入 letter 生成
- [ ] 改 prompt 的话粘一段生成的招呼语示例
```

## 安全红线

**永远不要提交这些文件**（已经在 `.gitignore` 但提醒一下）：

- `.env` —— 含 API key
- `assistant.json` —— 含 OpenAI assistant id
- `chrome_profile/` —— 含登录 cookie
- `vectorstores/` —— 含简历向量化结果
- `logs/` —— 含真实的 JD 和招呼语
- `resume/*.pdf` —— 含个人简历

如果不小心提交了 API key：**立刻去对应平台 revoke 那把 key 重发**，然后用
`git filter-repo` / `git filter-branch` 清历史 + 强推。

## 代码风格

- Python `>=3.11`，用 type hint
- 模块顶部用 docstring 写 **为什么需要这个文件**，函数 docstring 写
  **调用约定 + 边界 case**，不要写"What this function does"那种 ChatGPT 八股
- 注释解释 **为什么这么写**，不解释 **这行干了什么** —— 后者看代码就懂
- 业务路径用 `logging.getLogger(__name__)`，不要散落 `print()`
- 异常处理：要么处理完整（log + 兜底返回），要么 raise 给上层，不要写
  `except Exception: pass`
- 中文 / 英文 mix 没关系，但同一个模块内尽量保持一致

## 测试要求

- 新增公开函数：至少一个 happy-path 测试
- 修 bug：先写一个能复现 bug 的测试，再让它过
- `audit.py` / `utils/retry.py` / `audit/telemetry.py` 这类纯逻辑模块覆盖率应 ≥80%
- 浏览器自动化（`finding_jobs.py`）和真 LLM 调用属于 integration test，**不要 mock**
  去硬测，验证靠手动 `DRY_RUN`

## CI 通过条件

PR 合并前必须满足：

- [ ] `uv run pytest tests/ -v` 全过
- [ ] Smoke import check 全过（即所有核心模块能正常 import）
- [ ] `no-leak` job 通过（没有把敏感产物提进来）

## 跟 AI 协作（Claude / Copilot / Cursor）

允许用 AI 写代码，但是：

1. **代码合并前自己 review 一遍**。AI 经常把 `time.sleep(1)` 写成 `time.sleep(10)`
   这种细节，自己不读就 push 等于把 review 工作丢给 maintainer。
2. **AI 生成的注释/docstring 要瘦身**。"This function does X by calling Y" 这种
   废话不要留。
3. **不要把 Claude / Copilot 写进 commit 的 `Co-Authored-By` trailer** —— 这是
   仓库 owner 的明确偏好，理由：commit history 应该是人的署名。

## 维护者联系

- GitHub issue：日常问题首选
- @longsizhuo / @TinyAlmond：长期维护人

---

谢谢你愿意花时间帮忙。
