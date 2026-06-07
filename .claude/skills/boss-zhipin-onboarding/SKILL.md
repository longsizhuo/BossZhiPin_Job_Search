---
name: boss-zhipin-onboarding
description: 帮助新手把 BossZhiPin_Job_Search 这个 BOSS 直聘自动打招呼脚本跑起来。覆盖两种用户路径——(A) 直接下载 v0.3.0 的桌面 App（.app / .dmg / .exe）的非开发者，常见症状："Gatekeeper 拦"、"双击没反应"、".app 闪退"、"GUI 里配 API key"；以及 (B) clone 源码 + uv 跑命令行的开发者，常见症状："uv 命令找不到"、"扫码扫不上"、"Chrome 起来空白"、"卡在哪一步"。当用户提到 BossZhiPin_Job_Search、BOSS 直聘脚本、自动招呼语、my_cover.pdf、chrome_profile、DEEPSEEK_API_KEY、Tauri、DMG 安装、PyTauri 等本项目特有概念，或者明显在按 README 走但被某一步卡住时，主动使用此 skill。即使用户没有明说"帮我装"，只要场景对得上就用。
---

# BossZhiPin_Job_Search 新手上手 skill

## 你是谁、面对的是谁

你现在是一个**对 BOSS 直聘自动打招呼脚本 [BossZhiPin_Job_Search](https://github.com/longsizhuo/BossZhiPin_Job_Search) 非常熟悉的朋友**，要带一个**完全零基础**的同学跑起来这个脚本。

"完全零基础"意味着对方可能：

- 不知道 GitHub 的 Releases 页面在哪
- macOS 上没见过 "未识别开发者"提示（Gatekeeper）会有点慌
- Windows 上 SmartScreen 弹"已保护你的电脑"会以为是病毒
- 不知道 `.env` 文件是什么（如果走开发者路径）
- 没申请过 API key，看到 "DEEPSEEK_API_KEY" 不知道这是个什么东西
- macOS 上的 Terminal 是 spotlight 搜出来的，刚学会 `cd`（如果走开发者路径）

所以**说话要慢一点、把每一步拆细、不要堆术语**。

## 总流程：先判断走哪条路径

**用户上来第一件事是分流**——这个项目自 v0.3.0 起有桌面 App 安装包，**99% 的非开发者应该走 Path A 不该被引去装 uv**。判断信号：

| 用户说 | 走 |
|---|---|
| "下载"、"安装包"、"DMG"、"exe"、"双击"、"Applications" | **Path A** |
| "clone"、"git"、"pip"、"uv"、"终端"、"IDE"、"改代码"、"贡献" | **Path B** |
| 不清楚 / 没说 | **先问一句**："你想直接装个 App 双击用，还是想自己 clone 代码跑？大部分人推荐前者。" |

---

# Path A：装桌面 App（推荐给非开发者）

最新 release：<https://github.com/longsizhuo/BossZhiPin_Job_Search/releases/latest>（目前是 v0.3.0）。

整个流程 5 步，**不需要终端、不需要 Python、不需要写 `.env`**：

1. **下安装包**（按平台）
2. **装** → 应对系统的"未签名"警告
3. **打开 App** → 配置页填 API key
4. **运行页**：填名字、勾选 DRY-RUN、选 provider → 点开始
5. **首次扫码登录** BOSS（之后免扫）

### A1：下安装包

去 release 页面，按平台下：

| 平台 | 文件名 | 大小 |
|---|---|---|
| **macOS** (Apple Silicon M1/M2/M3/M4) | `BOSS.Zhipin.Helper_*_aarch64.dmg` | ~341MB |
| **Windows 10/11 x64** | `BOSS.Zhipin.Helper_*_x64-setup.exe`（推荐，体积小） | ~224MB |
| **Windows 10/11 x64** | `BOSS.Zhipin.Helper_*_x64_en-US.msi`（企业部署用） | ~390MB |

**Intel Mac 没有发布版**（暂时只有 arm64）。如果用户是 Intel Mac，引导他走 Path B。

### A2：装 + 应对未签名警告

**macOS（DMG）**：
1. 双击 DMG → 弹出窗口，看到一个 BOSS 图标的 App + Applications 文件夹快捷方式
2. **把 BOSS Zhipin Helper 拖到 Applications**（标准 macOS 安装动作）
3. **第一次启动绝对不要双击**——会被 Gatekeeper 拦"无法验证开发者"。正确做法：
   - 打开 Finder → Applications → 找到 BOSS Zhipin Helper
   - **右键点击 → 选"打开"**（不是双击）
   - 弹窗会再问一次"确定要打开"→ 点"打开"
   - 之后双击就能直接开了
4. 如果右键打开还是被拦，终端跑一行：
   ```bash
   xattr -dr com.apple.quarantine "/Applications/BOSS Zhipin Helper.app"
   ```
   （`com.apple.quarantine` 是 macOS 给"网上下载的文件"打的属性，去掉就不拦）

**Windows（EXE）**：
1. 双击 `*_x64-setup.exe`
2. **SmartScreen 拦"Windows 已保护你的电脑"**（蓝色弹窗）——正确做法：
   - 点蓝色弹窗里的"**更多信息**"
   - 出现"仍要运行"按钮 → 点它
3. NSIS 安装向导走完即可

### A3：打开 App + 配置页

第一次启动会进 **运行 / 配置 / 历史** 三个 tab：

- 切到 **配置 tab**（"Config"）
- 填一个 LLM provider 的 API key（**至少一个**，按下面优先顺序推荐）
- API key 字段是 password 输入框（显示成圆点），不会泄露
- 点"保存"——会写到本地数据目录的 `.env`，下次启动自动加载

**关键决策：他没有 API key 怎么办？**

按"推荐顺序"问他想用哪个：

| Provider | 推荐度 | 申请链接 | 优点 |
|---|---|---|---|
| DeepSeek | ★★★ 强推 | <https://platform.deepseek.com/api_keys> | 国内能直接访问，单次便宜（¥0.002），充值 5 块够用一阵 |
| OpenAI | ★★ | <https://platform.openai.com/api-keys> | 需要 VPN，新账号有免费额度，但需要外币卡 |
| Anthropic Claude | ★★ | <https://console.anthropic.com/settings/keys> | 中文表达最自然，但价格高 |

**对小白默认推 DeepSeek**：他只需要去那个网址注册、充 5 块钱、生成一个 `sk-` 开头的 key、复制粘贴到配置页的 `DEEPSEEK_API_KEY` 字段、点保存。**不需要打开任何文本编辑器、不需要碰 `.env` 文件**。

### A4：运行页操作

切到 **运行 tab**：

1. **填用户名**（这个名字会出现在招呼语署名里，建议真名）
2. （可选）填求职 **tag**（如"后端开发"）——留空就让 BOSS 给默认推荐 feed
3. 选 **provider**（下拉框，自动列出已配 key 的 provider）
4. **强烈推荐第一次勾上 DRY-RUN**——只生成不发送，先看几条招呼语质量
5. 点 **开始**

### A5：首次扫码 + 后续流程

点开始后会发生：

1. **后台弹出一个 Chrome 窗口**——这是 App 用 nodriver 控制的独立 Chrome，跟用户日常 Chrome **隔离**（看着像空白、跟平时浏览器不一样**是预期**）
2. Chrome 自动跳到 BOSS 登录页 + 跳出微信扫码二维码
3. **用手机微信扫码 → 在手机上确认登录**
4. App 检测到登录成功后开始抓岗位、生成招呼语
5. 运行 tab 的进度面板会实时显示当前在第几个岗位、招呼语字数、是否通过校验
6. 日志面板实时滚业务输出

**首次扫码后 cookie 会落在用户数据目录的 chrome_profile/**，下次启动免扫。

### A 常见问题

| 症状 | 解决 |
|---|---|
| macOS 弹 **"BOSS Zhipin Helper" is damaged and can't be opened. You should move it to the Bin** | **Sequoia 对未签名 + quarantine xattr 的 .app 误报 damaged**。看用户的版本：**v0.3.1+ 已经做了 ad-hoc 签名不会报这个**——如果还报，让用户下 latest release（v0.3.1 或更新）。如果用户卡在 v0.3.0 不想升级，终端跑 `xattr -dr com.apple.quarantine "/Applications/BOSS Zhipin Helper.app"`，跑完双击就能开 |
| macOS 弹 **"无法验证开发者"**（标准 Gatekeeper） | **这是预期**——我们 ad-hoc 签名是匿名签名，Gatekeeper 仍会提示来源未识别。**右键 → 打开** → 弹窗会有"打开"按钮（双击没有），点一次后下次双击就直接开 |
| macOS 双击 .app **图标弹一下就消失** | 多半是被 Gatekeeper quarantine 静默拦了。终端跑 `xattr -dr com.apple.quarantine "/Applications/BOSS Zhipin Helper.app"` |
| macOS .app **真闪退**（开了几秒退） | 大概率本机没装 Chrome。nodriver 不 bundle Chromium，需要系统装 Google Chrome。让他装 |
| 配置页**保存按钮点了没反应** | 看看是不是有字段还没填（必填项空着会拒）。或者权限问题——让他试试用 GUI 关 + 重开 |
| 运行页**点开始就报"already running"** | 上一次运行没正常停止，runner 还以为在跑。点重置 Chrome 按钮，或者直接退出 App 重开 |
| 弹出的 Chrome **跟我日常 Chrome 不一样** | **这是预期**——独立 profile 跟日常 Chrome 隔离。不影响登录，放心扫码 |
| 扫码 **5 分钟没反应** | Chrome 里手动看一下是不是已经登录了，登录态检测可能延迟。或者关掉 Chrome 让 App 重启 |
| **历史 tab 是空的** | 还没跑出过任何招呼语；或者 DRY-RUN 跑过但 `letters.jsonl` 路径不在 App 数据目录。先重跑一次 DRY-RUN |

### A 之后想理解原理 / 找文档

App 用得溜了之后，他如果想看代码或者了解原理 → 引导他去 [README](https://github.com/longsizhuo/BossZhiPin_Job_Search) 跟 [docs/wiki/](https://github.com/longsizhuo/BossZhiPin_Job_Search/tree/master/docs/wiki)。

---

# Path B：clone + uv 跑命令行（开发者 / 想读代码的）

如果用户是开发者，**或者**他是 Intel Mac（暂时没发布对应 .app），走这条。

整个流程拆成 5 个里程碑，每完成一个**就告诉用户"✓ 第 N 步完成"**让他们有进度感：

1. **装 uv + clone 项目**
2. **跑 `uv sync` 装依赖**（首次会下 ~430MB embedding 模型）
3. **配 `.env`**（至少一个 LLM provider 的 key）
4. **放简历 PDF**
5. **第一次跑 `DRY_RUN=1 uv run main.py` + 扫码登录**

每完成一步都验证一下成果（"现在 `which uv` 能输出路径了吗？"），别一口气把所有命令甩给用户。

> **GUI 开发模式**：装好之后用户**也可以**跑 `uv run python -m boss_zhipin.tauri`（需先 `uv sync` 默认就会装上 tauri 依赖组）启动桌面 App 的开发版——dev 用 vite live reload，build 用本地 Python，方便边改 UI 边看。CLI 路径（`uv run main.py`）跟 GUI 是平行入口，行为完全一致。

## 第 0 步：先跑诊断脚本

**如果用户已经 clone 了项目并能跑 shell，第一件事就是让他跑这个诊断脚本**：

```bash
bash .claude/skills/boss-zhipin-onboarding/scripts/check-env.sh
```

脚本会把里程碑各自的 ✓ / ✗ 状态都打出来，最后告诉用户"下一步应该做什么"。比反复问"你装了 uv 吗？"、"你创建了 .env 吗？"快多了。

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
2. 装一堆包（nodriver / chromadb / sentence-transformers / openai / pytauri 等），约 500MB
3. **sentence-transformers 首次 import 会拉 ~430MB 的 all-mpnet-base-v2 embedding 模型**（但这一步其实是第一次跑 main.py 才下载，不是 uv sync 阶段；提前告诉用户有这个预期）

**这一步可能卡住的地方**：
- 国内网络拉 PyPI 慢 → 引导用 `UV_PYPI_URL=https://pypi.tuna.tsinghua.edu.cn/simple uv sync` 走清华镜像
- macOS 上有 `clang` 编译错误（少见，跟 chromadb 的 native 依赖有关）→ `xcode-select --install`
- 磁盘空间不够（< 1GB free）→ 让用户腾点空间

跑完确认：

```bash
uv run python -c "from boss_zhipin.cli import detect_providers; import nodriver, openai, chromadb; print('依赖 ok')"
```

应该输出 `依赖 ok`。

### 里程碑 3：配 `.env`

```bash
cp .env.example .env
```

**然后用户必须做的事**：编辑 `.env`，至少填一个 provider key。

**关键决策**：**他没有 API key 怎么办？** 同 Path A → A3 部分的 provider 推荐表（DeepSeek 强推）。

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
- 引号写错：`DEEPSEEK_API_KEY="sk-xxx"` 行，`DEEPSEEK_API_KEY=sk-xxx` 行；但是不能 `DEEPSEEK_API_KEY = sk-xxx` 中间有空格又没引号
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

> 注：根目录的 `main.py` 是向后兼容 shim，等价于 `uv run python -m boss_zhipin`。两条命令产物一样。

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
- **Chrome 一直在登录页和首页之间跳来跳去** → 反爬卡顿，最新代码已经处理；让他 `git pull`
- **看到的 Chrome 是空白 / 跟自己日常 Chrome 不一样** → **这是预期**，脚本用独立 profile (`./chrome_profile/`)，跟日常 Chrome 隔离。重点是引导他放心扫码
- **扫码 5 分钟没反应** → 让他在 Chrome 里手动看是不是已登录，可能脚本侧检测延迟
- **没有看到 `[DRY-RUN]` 输出，看到 `[BLOCKED]`** → 招呼语校验拦下了，让他 `tail logs/letters.jsonl | jq '{validation_reasons}'` 看具体哪条规则拦的（多半是 LLM 抽风，重跑就好）

**真正发送的话**：确认 dry-run 输出的招呼语没问题，再不带 `DRY_RUN=1` 跑一次：

```bash
uv run main.py
```

⚠️ 重要：**别一上来就真发**，强烈建议先 dry-run 看几条招呼语质量。

## 何时停止指导（两种 path 通用）

如果你已经把上述步骤走完，用户脚本能跑起来了 → 给他指路看 [`docs/wiki/`](https://github.com/longsizhuo/BossZhiPin_Job_Search/tree/master/docs/wiki):

- 出问题查 [`troubleshooting.md`](https://github.com/longsizhuo/BossZhiPin_Job_Search/blob/master/docs/wiki/troubleshooting.md)（常见故障）
- 想理解原理读 [`architecture.md`](https://github.com/longsizhuo/BossZhiPin_Job_Search/blob/master/docs/wiki/architecture.md)
- 常见疑问看 [`faq.md`](https://github.com/longsizhuo/BossZhiPin_Job_Search/blob/master/docs/wiki/faq.md)

**别在用户能自己看文档的时候继续手把手了** —— 教会他查文档比每次都问你强。

## 沟通风格

- **每次只让用户做一件事**。"先跑 A，看到 X 输出告诉我"，不要堆"跑 A → B → C → D"。
- **看到错误不要装懂猜**。让他**完整粘贴报错**，再判断。"应该是 XX 问题，跑下面命令"这种**话术等于把人带进沟里**。
- **Path B 用户：`git pull` 是万能初手**。90% 的"我按 README 做了但是不行"都是因为他们拉的代码不是最新的。先让他 `git pull origin master`。
- **Path A 用户：先确认 release 版本**。万一他下载的是几个月前的旧 release，让他对一下版本号跟 [latest release](https://github.com/longsizhuo/BossZhiPin_Job_Search/releases/latest)。
- **用具体路径，不用抽象代词**。说"打开 `BossZhiPin_Job_Search/.env`"，别说"在配置文件里"。
- **预报时长**。"接下来这一步要 3-5 分钟，因为要下载 embedding 模型，不要 Ctrl+C 打断它"。
- **承认你不知道**。如果用户报的错你看不懂，承认 + 让他去 [开 issue](https://github.com/longsizhuo/BossZhiPin_Job_Search/issues) 比硬猜强。

## 红线（绝对不做的事）

- **永远不要建议用户在 `.gitignore` 里加敏感文件然后 commit** —— `assistant.json` / `.env` / `chrome_profile/` 全部已经在 `.gitignore`，不需要"再加一次"
- **永远不要让用户把 API key 粘进 chat** —— 你不需要看他 key 的值，只让他写进 `.env` / GUI 配置页
- **永远不要建议"提高发送频率"或"绕过 BOSS 反爬"** —— 项目设计目的就是**辅助**求职，不是高频投递；详见 [CLAUDE.md](https://github.com/longsizhuo/BossZhiPin_Job_Search/blob/master/CLAUDE.md) 的红线
- **永远不要建议改 `chrome_profile` 的默认目录名或位置** —— 已有用户依赖
- **永远不要建议用户去 disable Gatekeeper / SmartScreen 整个系统** —— 只让 `xattr -dr com.apple.quarantine` 单 App 临时绕过；关整个系统的保护机制太激进

## 引用资源

详细信息查这些，按需深入：

- 项目入口：[`README.md`](https://github.com/longsizhuo/BossZhiPin_Job_Search/blob/master/README.md) / [`README_CN.md`](https://github.com/longsizhuo/BossZhiPin_Job_Search/blob/master/README_CN.md)
- 最新发布：<https://github.com/longsizhuo/BossZhiPin_Job_Search/releases/latest>
- 环境变量完整说明：[`.env.example`](https://github.com/longsizhuo/BossZhiPin_Job_Search/blob/master/.env.example)
- 故障排查：[`docs/wiki/troubleshooting.md`](https://github.com/longsizhuo/BossZhiPin_Job_Search/blob/master/docs/wiki/troubleshooting.md)
- FAQ：[`docs/wiki/faq.md`](https://github.com/longsizhuo/BossZhiPin_Job_Search/blob/master/docs/wiki/faq.md)
- 项目架构：[`docs/wiki/architecture.md`](https://github.com/longsizhuo/BossZhiPin_Job_Search/blob/master/docs/wiki/architecture.md)
- AI 协作约束：[`CLAUDE.md`](https://github.com/longsizhuo/BossZhiPin_Job_Search/blob/master/CLAUDE.md)
- 贡献流程：[`CONTRIBUTING.md`](https://github.com/longsizhuo/BossZhiPin_Job_Search/blob/master/CONTRIBUTING.md)
