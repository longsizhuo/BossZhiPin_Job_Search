# 难 bug 的排查 playbook

把"主流程跑起来卡住、查了半天找不到原因"那一类 bug 的有效解法沉淀下来。基于
本仓库 2026-05-13 那次"nodriver `tab.evaluate` 莫名 hang"的真实排查经验
（一开始走了 5 轮弯路，最后用对方法 20 分钟定位 + 修好）。

适用场景：

- 浏览器自动化 / RPA / 网络请求 类项目里"调用没返回 / timeout / 死锁"
- 改了 selector / 改了 timeout / 换了 API 都救不回来的怪问题
- 看 log 看不出来"该到的地方没到，不该卡的地方卡了"

---

## 核心原则

**不要在主流程里反复改，写独立 probe 脚本验证。** 主流程跑一次成本高（启动浏览器、登录、跑到出问题的那一步要 30s+），probe 脚本只测最小复现路径，几秒一次。**5 次主流程迭代 ≈ 30 次 probe 迭代**，前者熬人后者熬代码。

**先找根因，再写补丁。** "加 timeout"、"加 try/catch"、"换 selector" 这些都是补丁，不是修复。补丁糊不上的时候说明你猜错了根因。

**bisect / 对比定位。** 找一个"已知能跑的版本"和"已知不能跑的版本"，逐项对比，差异处就是根因。

---

## 五步法

### 1. 复现 —— 让 bug 稳定出现

最便宜的"复现条件"是什么？

- 主流程跑全流程 → 太贵
- 改写一个最小 main 函数？→ 也贵
- 一个独立 probe 脚本，只跑出问题那段？→ **就它**

写 probe 之前问自己：**"复现这个 bug 至少需要哪些前提"**？
- 登录态？→ 复用 `chrome_profile/`
- 特定页面？→ 直接 `browser.get(url)` 跳过
- 之前的 N 步操作？→ **多半不需要**，bug 的"上下文"通常没你想的那么深

### 2. 隔离 —— 写 probe 脚本

放在 `scripts/probe_<topic>.py`。结构：

```python
# 复用已有 profile 启动 nodriver
config = Config()
config.user_data_dir = CHROME_PROFILE_DIR
browser = await uc.start(config=config)
tab = await browser.get(URL, new_window=True)
await asyncio.sleep(8)  # 给 SPA 足够时间 settle

# 阶段化测试：从最弱信号到最强信号
await try_eval("阶段 1: 1+1", tab, "1+1", timeout=5)              # CDP 通吗？
await try_eval("阶段 2: querySelector", tab, "...length", timeout=5)  # 简单查询
await try_eval("阶段 3: 复杂 IIFE", tab, FULL_JS, timeout=10)        # 复杂调用
await try_eval("阶段 4: 真实动作", tab, CLICK_JS, timeout=10)        # 跟主流程一样
```

**每个阶段独立 `try / timeout`，互不影响。** 阶段 3 炸不耽误阶段 4 继续测。每个阶段输出 **类型 + 内容 + 耗时**，方便对比。

底下附一张"结论查表"：

```
阶段 1 timeout       → channel 死了
阶段 1 ✓ 2 ✗       → 简单查询有问题（罕见）
阶段 1+2 ✓ 3 ✗     → 复杂 JS pattern 问题
全 ✓                → 问题不在 evaluate，在主流程上下文
```

实例：[`scripts/probe_click_card.py`](../../scripts/probe_click_card.py)

### 3. 假设 —— 一句话说清楚

写好 probe 跑一遍，看结果。然后**写一句完整的假设**：

> "tab.evaluate 在 BOSS 这页 hang，可能是 ___ 导致的"

如果你填不出来 ___ 那部分，**说明你还不懂 bug**，再多看一会儿日志。

不要急着改代码。改代码之前一定要能用一句话描述假设。

### 4. 验证 —— 用最便宜的实验证伪/证实假设

继续用 probe 脚本，**最好不要碰主流程**。

例：本次假设是"事件循环多次 enter/exit 导致 CDP 半死"。验证实验：

- ✅ probe 一个 `run_until_complete` 全程跑 → evaluate 秒返回
- ✅ 主流程多个 `_run` 串联 → evaluate 10s timeout

两个实验都用 **5 分钟内的可执行代码**完成。假设被坚实证实，根因锁定。

### 5. 修复 —— 在根因层动手，不要在症状层

根因层 = 改了之后**症状之外的相关问题也一起消失**。

本次根因 = "sync facade 跟 nodriver CDP 不兼容"。改了之后：
- `tab.evaluate` hang ✓ 修好
- `tab.xpath` hang ✓ 顺带修好
- `tab.select(timeout=0)` hang ✓ 顺带修好（之前另一个 commit 单独 work around 的）

如果你的修复**只解决了 1 个症状**没解决另外 2 个，你修的是症状不是根因。

---

## 给 AI 协作者（agent）的行动清单

按这个顺序做，**任何一步卡住超过 2 轮迭代就退回上一步**：

1. **先复现**。如果用户已经能复现了，重点听他描述的现象，**别上来就改代码**
2. **复述假设**。一句话："我猜是因为 ___ 导致 ___"。复述不出来 → 不动代码
3. **写 probe**。在 `scripts/probe_<topic>.py` 写**最小可复现**的脚本，**自己跑**（你在 user 本地）
4. **对比 probe 结果和主流程**。哪里不一样 = 根因候选
5. **改根因，不改症状**。一次只改一处。
6. **改完不要直接 commit**。落到文件、`git diff` 给 user 看、等他点头
7. **修复之后写一段 "怎么避免下次"**。比如"sync facade over async API"是反模式，记到 [feedback_*.md](.) memory

**反模式（自查清单）**：

- ❌ 一次跑主流程改一处选择器 / timeout / catch
- ❌ 让用户 re-run main.py 测"我新加的诊断 log"
- ❌ 写了一堆 try/except 把异常吞了，希望"绕过"
- ❌ 假设错了不退回去，继续往下补丁
- ❌ 没复述假设就上手改

## 给指挥方（user）的行动清单

驾驭 agent 的几个关键动作：

1. **看到 agent 第 2 次改主流程时，喊停**。问："你的假设是什么？为什么这次能修好上次没修好？" 如果回答模糊 → 让他写 probe。
2. **要求一句话根因**。"为什么会出这个 bug" 必须能用一句话讲清。讲不清说明 agent 还没懂。
3. **提醒 agent 本地能力**。Agent 在你机器上有 shell，能跑 `python` / `git` / `curl`。"你自己跑啊" 是合法指令。
4. **不让 agent 自己闭环**：
   - "改完别 commit，给我看 diff"
   - "跑一次给我看输出"
   - "为什么这么改"
5. **对每个'修好了'要求实证**。新跑一次主流程的输出 / 新的 probe 结果 / 单测全过 —— 没实证别相信。
6. **追问 N 个症状**。"这个改动除了修 A，能修 B 和 C 吗？" 修不了 → 多半是症状级补丁，让他再想。

**何时干预**：

- agent 第 3 次说"这次应该 OK 了" → 让他写 probe 验证后再说
- agent 改了 selector / timeout / try-catch 三件套 → 让他先停下复述假设
- agent 让你 re-run main.py 测 → 反问"你能在你本地跑吗"

---

## 反例：本次 bug 的弯路记录

时间线（每一步都没修好）：

1. **第 1 轮**：发现 `_get_job_description_by_index` 抓不到，怀疑选择器过期。改了 xpath → 没用。补丁，没找根因。
2. **第 2 轮**：以为新 xpath 在 BOSS DOM 上不对，让 user 在 DevTools 跑 `$x(...)` 验证 → 折腾半小时（DevTools 接错 tab 等）。**绕路**，本可以让脚本自己 dump HTML。
3. **第 3 轮**：写 `dump_boss_page.py` 抓了 HTML，证实 xpath 对的。但还是觉得是"page 没 settle"，加 5s sleep + 加大 timeout → 还是 timeout。**继续补丁**。
4. **第 4 轮**：怀疑是 `tab.xpath` hang，改成 `tab.evaluate(JS)` → **同样 timeout**。这时该意识到"不是 API 的问题"，但没意识到。
5. **第 5 轮**：user 直接命令"自己写 python 脚本"。写 `probe_click_card.py`，跑出来发现 evaluate **秒返回**。
6. **顿悟**：probe 一个 `run_until_complete`、主流程多次 `_run`，唯一差异在事件循环结构。根因锁定 → async 重构 → 完美工作。

**教训**：

- 第 1-4 轮全在"猜 + 补丁 + 让 user 测"循环里，浪费了 ~1 小时
- 第 5 轮 user 强行让 agent 写 probe，**20 分钟解决**
- **如果第 2 轮就直接写 probe，至少省 40 分钟**

---

## 相关资源

- [`scripts/dump_boss_page.py`](../../scripts/dump_boss_page.py) — 抓页面 HTML + 截图 + 自动探测候选选择器
- [`scripts/probe_click_card.py`](../../scripts/probe_click_card.py) — 分阶段测 evaluate / click / 读 JD
- [`.claude/skills/boss-zhipin-onboarding/scripts/check-env.sh`](../../.claude/skills/boss-zhipin-onboarding/scripts/check-env.sh) — 一次性诊断 5 个里程碑状态

下次遇到类似 bug：**先来这页翻一眼，再动手**。
