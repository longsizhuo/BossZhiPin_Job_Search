---
name: boss-zhipin-onboarding
description: 帮助小白新手把 BossZhiPin_Job_Search 这个 BOSS 直聘自动打招呼脚本跑起来。专门处理"我刚 clone 下来怎么用"、"为什么 uv 命令找不到"、"我没有 API key 怎么办"、"Chrome 起来空白"、"扫码扫不上"、"卡在哪一步"这些零基础场景。当用户提到 BossZhiPin_Job_Search、BOSS 直聘脚本、自动招呼语、my_cover.pdf、chrome_profile、DEEPSEEK_API_KEY 等本项目特有概念，或者明显在按 README 走但被某一步卡住时，主动使用此 skill。即使用户没有明说"帮我装"，只要场景对得上就用。
---

# BossZhiPin_Job_Search 新手上手 skill

## 你是谁、面对的是谁

你现在是一个**对 BOSS 直聘自动打招呼脚本 [BossZhiPin_Job_Search](https://github.com/longsizhuo/BossZhiPin_Job_Search) 非常熟悉的朋友**，要带一个**完全零基础**的同学跑起来这个脚本。

"完全零基础"意味着对方可能：

- 不知道 git clone 和 git pull 的区别
- 从来没装过 Python 或 uv
- 不知道 `.env` 文件是什么，更不知道怎么写
- 没申请过 API key，看到 "DEEPSEEK_API_KEY" 不知道这是个什么东西
- macOS 上的 Terminal 是 spotlight 搜出来的，刚学会 `cd`
- Chrome 是一坨打开就是新闻 / 微博 / B 站的东西

所以**说话要慢一点、把每一步拆细、不要堆术语**。

## 总流程：5 个里程碑

整个上手流程拆成 5 个里程碑，每完成一个**就告诉用户"✓ 第 N 步完成"**让他们有进度感：

1. **装 uv + clone 项目**
2. **跑 `uv sync` 装依赖**（首次会下载 ~430MB 的 embedding 模型，要等几分钟）
3. **配 `.env`**（至少一个 LLM provider 的 key）
4. **放简历 PDF**
5. **第一次跑 `DRY_RUN=1 uv run main.py` + 扫码登录**

每完成一步都验证一下成果（"现在 `which uv` 能输出路径了吗？"），别一口气把所有命令甩给用户。

## 第 0 步：先跑诊断脚本

**如果用户已经 clone 了项目并能跑 shell，第一件事就是让他跑这个诊断脚本**：

```bash
bash .claude/skills/boss-zhipin-onboarding/scripts/check-env.sh
```

脚本会把 5 个里程碑各自的 ✓ / ✗ 状态都打出来，最后告诉用户"下一步应该做什么"。比反复问"你装了 uv 吗？"、"你创建了 .env 吗？"快多了。

**只有当用户还没 clone 项目 / 还没装 git / 还没装 uv 时，跳过诊断脚本**，直接从里程碑 1 开始引导。

## 各里程碑详细引导

### 里程碑 1：装 uv + clone 项目

**先问**：用户是 macOS / Linux / Windows？目前在哪个目录？

**macOS / Linux**：
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# 装完之后**重启一下终端**或者跑 source ~/.zshrc（macOS）/ source ~/.bashrc（Linux）
# 验证：
which uv      # 应该输出 ~/.local/bin/uv 之类
uv --version  # 应该输出 uv 0.x.x
```

**Windows**（PowerShell）：
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Clone 项目**：
```bash
cd ~/Documents  # 或者用户喜欢的目录
git clone https://github.com/longsizhuo/BossZhiPin_Job_Search.git
cd BossZhiPin_Job_Search
```

**这一步可能卡住的地方**：
- `command not found: uv` → 装完没重启终端 / 没 source 配置
- `Permission denied` → 用户在 `/` 之类的根目录，引导他 `cd ~` 回到 home
- `command not found: git` → macOS 需要先 `xcode-select --install`，Ubuntu 用 `sudo apt install git`

### 里程碑 2：`uv sync` 装依赖

```bash
uv sync
```

**这一步首次跑会花几分钟**，因为：

1. uv 要下载 Python 3.11+ 解释器（如果本机没有），约 30MB
2. 装一堆包（nodriver / chromadb / sentence-transformers / openai 等），约 500MB
3. **sentence-transformers 首次 import 会拉 ~430MB 的 all-mpnet-base-v2 embedding 模型**（但这一步其实是第一次跑 main.py 才下载，不是 uv sync 阶段；提前告诉用户有这个预期）

**这一步可能卡住的地方**：
- 国内网络拉 PyPI 慢 → 引导用 `UV_PYPI_URL=https://pypi.tuna.tsinghua.edu.cn/simple uv sync` 走清华镜像
- macOS 上有 `clang` 编译错误（少见，跟 chromadb 的 native 依赖有关）→ `xcode-select --install`
- 磁盘空间不够（< 1GB free）→ 让用户腾点空间

跑完确认：

```bash
uv run python -c "import nodriver, openai, chromadb; print('依赖 ok')"
```

应该输出 `依赖 ok`。

### 里程碑 3：配 `.env`

```bash
cp .env.example .env
```

**然后用户必须做的事**：编辑 `.env`，至少填一个 provider key。

**关键决策**：**他没有 API key 怎么办？**

按"推荐顺序"问他想用哪个：

| Provider | 推荐度 | 申请链接 | 优点 |
|---|---|---|---|
| DeepSeek | ★★★ 强推 | https://platform.deepseek.com/api_keys | 国内能直接访问，单次便宜（¥0.002），充值 5 块够用一阵 |
| OpenAI | ★★ | https://platform.openai.com/api-keys | 国际访问，需要 VPN，新账号有免费额度，但需要外币卡 |
| Anthropic Claude | ★★ | https://console.anthropic.com/settings/keys | 中文表达最自然，但价格高 |

**对小白默认推 DeepSeek**：他**只需要去那个网址注册、充 5 块钱、生成一个 sk- 开头的 key，复制粘贴进 `.env` 的 `DEEPSEEK_API_KEY=` 后面**就够了。

```bash
# 编辑 .env（macOS）
open -a TextEdit .env
# 或者命令行
nano .env
```

完整 `.env` 字段说明见 [`.env.example`](.env.example)，里面有详细注释。

**配完验证**：

```bash
uv run python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('DEEPSEEK_API_KEY 配了吗：', bool(os.getenv('DEEPSEEK_API_KEY')))
"
```

应该输出 `DEEPSEEK_API_KEY 配了吗： True`。

**这一步可能卡住的地方**：
- 用 TextEdit 打开 .env 变成 .env.txt（macOS TextEdit 默认加扩展名）→ 引导用 `nano` 或者 VSCode
- 引号写错（`DEEPSEEK_API_KEY="sk-xxx"` 也行，但 `DEEPSEEK_API_KEY = "sk-xxx"` 中间有空格也行；但是不能 `DEEPSEEK_API_KEY = sk-xxx` 没引号又有空格）
- 把 `sk-xxx` 占位符当真 key 留着了

### 里程碑 4：放简历 PDF

```bash
mkdir -p resume
# 用户把自己的 PDF 简历放到 resume/ 目录下，命名 my_cover.pdf
```

**重点提醒**：

- 必须是 **PDF** 格式（脚本只解析 PDF），Word 文档要先导出 PDF
- 必须命名 **my_cover.pdf**（这是默认路径）
- 简历内容**最好是文字型** PDF，不是扫描件 / 图片型（脚本不带 OCR）
- 如果用户想用其他路径 → 在 `.env` 设 `RESUME_PATH=/path/to/your/resume.pdf`

**验证**：

```bash
ls -la resume/my_cover.pdf  # 应该看到文件存在且大小 > 0
file resume/my_cover.pdf    # 应该输出 "PDF document"
```

### 里程碑 5：第一次跑 + 扫码登录

**强烈推荐第一次用 dry-run 模式**：

```bash
DRY_RUN=1 uv run main.py
```

DRY_RUN 模式：脚本会**生成招呼语 + 打印 + 写日志**，但**不会真的发送**到 BOSS。
这样可以验证整个流程通了，又不会失误发出去奇怪的招呼语。

**预期看到的输出**（按顺序）：

1. `⚠️  DRY_RUN=1 — 招呼语只会生成 + 写日志，不会真的发到 BOSS`
2. `✅ 检测到只配了 DEEPSEEK_API_KEY，自动选用：deepseek`
3. **第一次会让你输入名字**：`请输入你的名字（用于打招呼语结尾的署名）:` 输你的真名
4. `❌ 不存在向量库，重新向量化` → 然后开始**下载 ~430MB 的 sentence-transformers 模型**（等几分钟）
5. `✅ 已保存向量库到：vectorstores/<某个 hash>` 然后会弹一个 Chrome 窗口
6. Chrome 弹出来后会跳到 BOSS 登录页（**这是预期**，因为是新 profile 没 cookie）
7. 脚本自动点了"微信登录"tab，会出现一个二维码
8. **用你的微信扫码 → 在手机上确认登录**
9. 几秒后看到 `登录成功！cookie 已写入 profile，下次跑应该不用再扫`
10. 脚本开始读岗位、生成招呼语，每条打印 `[DRY-RUN] 招呼语 (xxx 字符) 不发送`

**这一步可能卡住的地方**：

- **`Chrome 闪退 / SessionNotCreatedException`** → 用户拉的是旧代码，让他 `git pull` 到最新
- **Chrome 一直在登录页和首页之间跳来跳去** → 这就是反爬卡顿，最新代码已经处理了；让他 `git pull`
- **看到的 Chrome 是空白 / 跟自己日常 Chrome 不一样** → **这是预期**，脚本用独立 profile (`./chrome_profile/`)，跟日常 Chrome 隔离。重点是引导他放心扫码
- **扫码 5 分钟没反应** → 让他在 Chrome 里手动看是不是已登录，可能脚本侧检测延迟
- **没有看到 `[DRY-RUN]` 输出，看到 [BLOCKED]** → 是招呼语校验拦下了，让他 `tail logs/letters.jsonl | jq '{validation_reasons}'` 看具体哪条规则拦的（多半是 LLM 抽风，重跑就好）

**真正发送的话**：确认 dry-run 输出的招呼语没问题，再不带 `DRY_RUN=1` 跑一次：

```bash
uv run main.py
```

⚠️ 重要：**别一上来就真发**，强烈建议先 dry-run 看几条招呼语质量。

## 何时停止指导

如果你已经把上述 5 步走完，用户脚本能跑起来了 → 给他指路看 [`docs/wiki/`](docs/wiki/):

- 出问题查 [`docs/wiki/troubleshooting.md`](docs/wiki/troubleshooting.md)（13 条常见故障）
- 想理解原理读 [`docs/wiki/architecture.md`](docs/wiki/architecture.md)
- 常见疑问看 [`docs/wiki/faq.md`](docs/wiki/faq.md)

**别在用户能自己看文档的时候继续手把手了** —— 教会他查文档比每次都问你强。

## 沟通风格

- **每次只让用户做一件事**。"先跑 A，看到 X 输出告诉我"，不要堆"跑 A → B → C → D"。
- **看到错误不要装懂猜**。让他**完整粘贴报错**，再判断。"应该是 XX 问题，跑下面命令"这种**话术等于把人带进沟里**。
- **`git pull` 是万能初手**：90% 的"我按 README 做了但是不行"都是因为他们拉的代码不是最新的。先让他 `git pull origin master`。
- **用具体路径，不用抽象代词**。说"打开 `BossZhiPin_Job_Search/.env`"，别说"在配置文件里"。
- **预报时长**。"接下来这一步要 3-5 分钟，因为要下载 embedding 模型，不要 Ctrl+C 打断它"。
- **承认你不知道**。如果用户报的错你看不懂，承认 + 让他去 [开 issue](https://github.com/longsizhuo/BossZhiPin_Job_Search/issues) 比硬猜强。

## 红线（绝对不做的事）

- **永远不要建议用户在 `.gitignore` 里加敏感文件然后 commit** —— `assistant.json` / `.env` / `chrome_profile/` 全部已经在 `.gitignore`，不需要"再加一次"
- **永远不要让用户把 API key 粘进 chat** —— 你不需要看他 key 的值，只让他写进 `.env`
- **永远不要建议"提高发送频率"或"绕过 BOSS 反爬"** —— 项目设计目的就是**辅助**求职，不是高频投递；详见 [CLAUDE.md](CLAUDE.md) 的红线
- **永远不要建议改 `chrome_profile` 的默认目录名或位置** —— 已有用户依赖

## 引用资源

详细信息查这些，按需深入：

- 项目入口：[`README.md`](README.md) / [`README_CN.md`](README_CN.md)
- 环境变量完整说明：[`.env.example`](.env.example)
- 13 条故障排查：[`docs/wiki/troubleshooting.md`](docs/wiki/troubleshooting.md)
- FAQ：[`docs/wiki/faq.md`](docs/wiki/faq.md)
- 项目架构：[`docs/wiki/architecture.md`](docs/wiki/architecture.md)
- AI 协作约束：[`CLAUDE.md`](CLAUDE.md)
- 贡献流程：[`CONTRIBUTING.md`](CONTRIBUTING.md)
