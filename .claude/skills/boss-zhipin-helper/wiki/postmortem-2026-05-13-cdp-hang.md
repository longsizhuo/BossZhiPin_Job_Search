# 复盘：nodriver CDP 在 sync facade 下随机 hang

- **发生日期**：2026-05-13
- **症状用户感知时长**：~36 小时（断断续续）
- **实际排查耗时**：从锁定根因 → 修复 ~20 分钟
- **走的弯路时长**：~1.5 小时（4-5 轮补丁式尝试，全部失败）
- **影响**：`DRY_RUN=1 uv run main.py` 在第 1 个岗位处死循环超时，没法生成任何招呼语

## TL;DR

`website_oper/finding_jobs.py` 用 sync facade 模式（每个公开同步函数内部
`uc.loop().run_until_complete(coro)`）跟 async 的 nodriver 做适配。**这个模式
跟 nodriver 的 CDP 长连接根本不兼容**：事件循环每次 enter/exit，CDP websocket
的内部状态机就错位一次，第二次 `tab.evaluate(...)` 永远等不到响应、永远卡住。

修复 = **删掉 sync facade，全链路 async**，main.py 入口处 `uc.loop()
.run_until_complete(send_job_descriptions_to_chat(...))` 一次性跑完所有
浏览器 + LLM 调用。

---

## 1. 症状

`DRY_RUN=1 uv run main.py` 输出：

```
01:09:32 页面已稳定，当前URL: https://www.zhipin.com/web/geek/jobs?ka=header-job-recommend
01:09:32 再等 5s 让 Vue 把 JS 跑顺...
01:09:37 检测到已登录
01:09:37 [select_dropdown_option] label 为空，沿用当前推荐 feed
01:09:37 === 第 1 轮: 处理 job_index=1 ===
01:09:37 [get_job_description_by_index] index=1
01:09:47 [WARNING] evaluate 超过 10s 没返回（JS: JSON.stringify(...)）
01:09:47   点击 .job-card-box[1]: {}
01:09:47 job_index=1 拿不到 JD（连续第 1 次）
01:09:50 === 第 2 轮: 处理 job_index=2 ===
01:09:50 [get_job_description_by_index] index=2
01:10:00 [WARNING] evaluate 超过 10s 没返回...
...
```

每一轮**都精确卡 10 秒到 timeout，无一例外**。点击没成功，JD 读不到，重试 5
次后判断"feed 到底"提前退出。

关键反直觉点：

- xpath / CSS selector **都验证过有效**（dump 出来的 HTML 用 lxml 跑 xpath 命中 15 个 `.job-card-box`）
- `tab.evaluate("1+1")` 在 dump 脚本里**秒返回**
- 同样的代码、同样的 profile，**只有主流程会卡，独立 probe 不会卡**

---

## 2. 错误假设的弯路（4 轮）

### 弯路 1：以为是 BOSS 改了 DOM

第一直觉：BOSS 升级前端，老 xpath 失效。

- 写了 `scripts/dump_boss_page.py` 抓 HTML + 截图 + 候选选择器探测
- 用 grep / lxml 在 HTML 里翻新 class 名 → 找到 `.job-card-box`、`.job-detail-body`
- 改 `finding_jobs.py` 用新选择器 → **跑还是 timeout**

**为什么没修好**：新 xpath 是对的，问题不在 xpath 本身。但 timeout 让人继续往
"选择器还是不对"方向猜。

### 弯路 2：以为是 nodriver `tab.xpath()` 的 timeout 不可靠

之前确实见过 `tab.select(timeout=0)` hang 的现象，所以怀疑 `tab.xpath` 也有同
样毛病。

- 把 `_get_job_description_by_index_impl` 整段重写，从 `tab.xpath()` 换到
  `tab.evaluate(JS)` —— 在浏览器内部直接 `document.querySelectorAll(...).click()`
- 写得很扎实：`asyncio.wait_for` 兜底超时、JSON 解析容错、`_js_click_at_index`
  和 `_js_wait_text` 两个 helper、JS 内层 try/catch 包错误返回 `{ok:false, error:...}`
- 跑 → **同样 10s timeout**

**为什么没修好**：换 API 不能解决"channel 死了"的问题。`tab.xpath` 跟
`tab.evaluate` 走同一个 websocket。

### 弯路 3：以为是 Vue 还没渲染完

dump 脚本 `await asyncio.sleep(8)` 后跑得稳，主流程只 `_wait_url_stable(2.0)`
就开始抓 → 觉得是给 Vue 的时间不够。

- `_open_browser_impl` 末尾再加 `await asyncio.sleep(5)`
- 重跑 → **同样 10s timeout**

**为什么没修好**：sleep 期间事件循环只在那一次 `_run` 里活着，sleep 结束后
`_open_browser_impl` 返回，事件循环 exit。下次 `get_job_description_by_index`
进入新的 `_run`，CDP 还是半死状态。**sleep 治不了"事件循环停顿"。**

### 弯路 4：用 user 当测试床

每次改一处，让 user `git pull` + `DRY_RUN=1 uv run main.py`，等 30s+ 看日志。
跑 5 轮就是 ~3 分钟（中间还要 user 操作）。

**为什么慢**：feedback loop 太长。一个改动验证一次假设要 user 配合，每次代价
都很高。**应该写 probe 自己跑**。

---

## 3. 找到根因（第 5 轮）

User 直接说**"你直接写一个 python 脚本抓取不就行了？一定要写到主链路里让我去
测试"**。

写了 `scripts/probe_click_card.py`：复用 `chrome_profile/` 登录态，分 5 个阶段
独立测试 `tab.evaluate` 各种打法（1+1 → querySelector → IIFE → click → 等 JD）。

跑了一次，**5 个阶段全部秒过**：

```
[阶段 1: 1+1]                    ✓ 0.01s | type=int | result=2
[阶段 2: querySelectorAll]        ✓ 0.00s | type=int | result=15
[阶段 3: 复杂 IIFE 查询]          ✓ 0.00s | type=str | result='{"url":...,"cards":15,...}'
[阶段 4: 点击 .job-card-box[0]]   ✓ 0.01s | type=str | result='{"ok":true,"total":15}'
[阶段 5: 点击后读 JD]             ✓ 0.00s | type=str | result='{"cards":15,"detail_text_len":1224,...}'
```

**问题不在 evaluate**。

然后用 Bash 直接复现主流程：`uv run main.py` —— **同样的 evaluate 调用、同样的页面、同样的 nodriver**，全部 10s timeout。

唯一差异：**probe 用一个 `run_until_complete(main())` 全程跑完；主流程跑三个 `_run(coro)`**。

根因锁定。

---

## 4. 根因解释

nodriver 跟 Chrome 的通信走 **CDP (Chrome DevTools Protocol) over websocket**：

```
你的 Python 代码
    │
    ▼ await tab.evaluate("...")
nodriver 发送 CDP 请求 {"id": 42, "method": "Runtime.evaluate", ...}
    │
    ▼ over websocket
Chrome 处理 → 返回 {"id": 42, "result": ...}
    │
    ▼ websocket 收到响应
nodriver 的 background reader task 把响应跟请求 id 配对
    │
    ▼ 唤醒等待 id=42 的 Future
你的 await 拿到结果返回
```

关键：**那个 background reader task 是 asyncio.Task，只在事件循环运行时才被调度**。

旧 sync facade 长这样：

```python
def open_browser_with_options(url, browser):
    return uc.loop().run_until_complete(_open_browser_impl(url))
    # ^^ 事件循环进入、跑到 _impl 返回、退出

def log_in():
    return uc.loop().run_until_complete(_log_in_impl())
    # ^^ 事件循环再次进入、退出

def get_job_description_by_index(index):
    return uc.loop().run_until_complete(_get_job_description_by_index_impl(index))
    # ^^ 第三次进入、卡死
```

**两次 `run_until_complete` 之间，事件循环停止运转**。

这段时间发生什么：

- websocket 上 Chrome 发的消息**继续到达**（OS-level 缓冲）
- nodriver reader task **没被调度**（loop 没在跑）
- 当下一次 `run_until_complete` 进来时，reader task 醒过来开始处理
- **但消息处理顺序乱了**：reader 期待响应 sequence 跟当前发请求的 sequence 已经对不上
- 状态机错位，下一次 `tab.evaluate` 发出的请求**永远等不到匹配的 response**
- 我们的 `asyncio.wait_for(timeout=10)` 强行超时，TimeoutError 上报

**类比**：CDP 是一通电话，你和 Chrome 一直在通话。sync facade 相当于
**每发一句话就挂机，下次再拨**。Chrome 那边以为通话已结束、新的拨号信号乱了，
你听到的就是无尽嘟嘟声（timeout）。

---

## 5. 修复

把整段流程改成**一条 async 调用链，只 `run_until_complete` 一次**。

### 5.1 `website_oper/finding_jobs.py`

删 `_run` 和所有 sync wrapper。公开函数全部 `async def`：

```python
# 改前
def open_browser_with_options(url, browser):
    if browser != "chrome":
        raise NotImplementedError(...)
    _run(_open_browser_impl(url))

# 改后
async def open_browser_with_options(url: str, browser: str) -> None:
    if browser != "chrome":
        raise NotImplementedError(...)
    # 直接是之前 _impl 的内容
    ...
```

涉及函数：`open_browser_with_options`、`log_in`、`select_dropdown_option`、
`get_job_description_by_index`、`get_text_by_css`、`click_by_xpath`、
`wait_for_css`、`send_chat_message`、`navigate_back`。

### 5.2 `website_oper/write_response.py`

`send_job_descriptions_to_chat` 改 `async def`，调用方加 `await`，`time.sleep`
→ `await asyncio.sleep`：

```python
async def send_job_descriptions_to_chat(...) -> None:
    await finding_jobs.open_browser_with_options(url, browser_type)
    await finding_jobs.log_in()
    await finding_jobs.select_dropdown_option(label)

    while True:
        job_description = await finding_jobs.get_job_description_by_index(job_index)
        if job_description:
            # LLM 调用是同步阻塞的 HTTP 请求，扔到 thread pool 跑
            # 避免阻塞事件循环 → 卡死 nodriver CDP heartbeat
            response = await asyncio.to_thread(
                generate_letter,
                usr_name, vectorstore, job_description, model=models,
            )
            ...
        await asyncio.sleep(3)
        job_index += 1
```

**关键细节**：LLM 调用（`generate_letter` / `chat`）是同步阻塞的，直接 `await`
不能用。包 `asyncio.to_thread(...)` 扔到线程池里跑 —— **不是为了并发，是为了
不阻塞主事件循环**，让 nodriver reader task 在 LLM 调用的几秒里继续工作。如果
不这么做，LLM 调用的 3-5 秒里事件循环阻塞，CDP 又死了。

### 5.3 `main.py`

三处 `send_job_descriptions_to_chat(...)` 包成
`uc.loop().run_until_complete(...)`：

```python
import nodriver as uc
...
if provider == "deepseek":
    vectorstore = embed_pdf(resume_path, "./vectorstores")
    uc.loop().run_until_complete(send_job_descriptions_to_chat(
        usr_name, url, browser_type, label, "deepseek",
        vectorstore=vectorstore, dry_run=dry_run,
    ))
elif provider == "chatgpt": ...
elif provider == "claude": ...
```

**整段必须一个 `run_until_complete` 跑完**。在这里面，浏览器操作、LLM 调用、
sleep、日志写入全部按 async 顺序执行；事件循环不再停顿。

---

## 6. 验证

重跑 `DRY_RUN=1 uv run main.py`，**75 秒内连刷 7 个岗位**：

```
01:25:21 [get_job_description_by_index] index=1
01:25:21   点击 .job-card-box[1]: {'ok': True, 'total': 15}   ← 0 秒！
01:25:21   JD 长度 2346 字符
01:25:21 chat 按钮文字: '立即沟通'
01:25:35 [DRY-RUN] 招呼语 (255 字符) 不发送
01:25:38 === 第 2 轮: 处理 job_index=2 ===
01:25:38   点击 .job-card-box[2]: {'ok': True, 'total': 15}   ← 0 秒
01:25:39   JD 长度 1646 字符
01:25:43 [DRY-RUN] 招呼语 (371 字符) 不发送
... 一直刷到第 7 轮，全部正常
```

每轮 ~8 秒（含 DeepSeek API 调用），相比修复前每轮 10 秒纯超时 + 0 输出，**整条
链路从死到活**。59 个 pytest 单测全过（纯逻辑测试不受 async 改动影响）。

---

## 7. 为什么之前的尝试都没用

| 尝试 | 期望解决 | 实际结果 | 为什么没用 |
|---|---|---|---|
| 改 xpath 用新 class | DOM 已变 | 还是 timeout | 选择器对的，根因不在 selector |
| 换 `tab.evaluate(JS)` | `tab.xpath()` 不可靠 | 一样 timeout | 同一 websocket，channel 死了换 API 没用 |
| `try/catch` 包 JS | JS 抛异常被吞 | 一样 timeout | JS 根本没执行（response 没回） |
| 加 5s 额外 sleep | Vue 还没 ready | 一样 timeout | sleep 在 `_run` 里、出 `_run` 后 channel 还是死 |
| 加大 timeout 5→10s | 等再久点 | 还是 timeout | response 永远不来，等到天荒地老也没用 |

**所有补丁都在"治 evaluate 调用本身"，但 bug 在"调用之间的事件循环管理"。**
治错了层。

---

## 8. 经验教训

### 8.1 对项目的影响

`docs/wiki/adr/001-nodriver-over-selenium.md` 当时说"sync facade + async impl"
是合理设计。**这次复盘推翻了那个结论**：sync facade over nodriver async API 是
反模式，不能用。下次升级 ADR-001 时要补这一节。

类似的 async-only 库还有 [Playwright](https://playwright.dev/python/) —— 它的
`playwright-python` 提供 sync API 但**内部用一个常驻线程跑 event loop**，不是
裸 `run_until_complete` facade 模式。如果项目以后要换 Playwright，参考它的实现
方式比手糊 sync facade 安全。

### 8.2 通用调试原则

详见 [debugging-playbook.md](debugging-playbook.md)，本次踩中的所有反模式都列
了。简短回顾：

1. **同一个 bug 第 2 次补丁失败 → 退回去重新形成假设**。不要继续往下补，先想
   清楚根因是什么。
2. **写 probe 比改主流程快 10 倍**。本次 1.5 小时弯路 vs 20 分钟根因定位，差距
   就在这。
3. **Agent 在用户本地，自己跑别让用户当测试床**。除非操作本身需要用户介入
   （扫码、下卡），否则 agent 应该自己 `uv run ...` 直接看结果。
4. **bisect 思维**：找到"已知能跑的"（probe）和"已知不能跑的"（main），逐项
   对比差异。本次差异是"事件循环进入次数"，这就是根因候选。

### 8.3 仪式 vs 实质

之前**对 ADR-001 / nodriver 选型有充分讨论**（沟通几小时），但**没人想过 sync
facade 的可行性边界**。这个 bug 暴露了一个盲点：**项目结构决策（async vs
sync）跟库的实现细节（CDP 是 stateful 长连接）有耦合，不能纯凭 API 表面签名
决定**。

下次引入 async 库时增加一项 check：

> 这个库的 async 是"语法糖"（每次调用独立），还是"持续状态"（依赖事件循环
> 持续运行）？后者**不能**用 sync facade，必须全链路 async。

判断方法：看库内部是否有 `asyncio.create_task` 起 background reader / writer /
heartbeat task。nodriver 有（CDP reader）、Playwright 有（CDP reader）、
`httpx.AsyncClient` 没有（每次请求独立）。

---

## 9. 相关文件

- 修复 commit（待 commit）：`website_oper/finding_jobs.py` + `website_oper/write_response.py` + `main.py`
- 帮我找到根因的 probe：[`scripts/probe_click_card.py`](../../scripts/probe_click_card.py)
- HTML dump 工具：[`scripts/dump_boss_page.py`](../../scripts/dump_boss_page.py)
- 通用调试方法论：[`debugging-playbook.md`](debugging-playbook.md)
- 浏览器选型 ADR（待补 sync-facade 反例）：[`adr/001-nodriver-over-selenium.md`](adr/001-nodriver-over-selenium.md)
