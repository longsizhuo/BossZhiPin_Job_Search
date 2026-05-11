# ADR-001：浏览器自动化用 nodriver 而不是 Selenium / undetected-chromedriver

- **状态**：已采纳
- **日期**：2026-05-11
- **决策人**：longsizhuo
- **相关 commit**：[`e83e314`](https://github.com/longsizhuo/BossZhiPin_Job_Search/commit/e83e314)
  (langchain 移除) + [`eda7af4`](https://github.com/longsizhuo/BossZhiPin_Job_Search/commit/eda7af4)
  (Selenium → nodriver)

## 背景

项目最初基于 Selenium。2026-05 长时间手测发现：

1. BOSS 直聘的反爬识别到 Selenium 后会把页面**强制重定向**到 `data:,`（空白页）
   或直接 `window.close()` tab。
2. 加上 `navigator.webdriver` 屏蔽、`excludeSwitches=enable-automation`、
   `useAutomationExtension=False`、`--disable-blink-features=AutomationControlled`
   这一套标准反检测三件套，**也只是把"立刻被踢"延长到"15 秒后被踢"**。
3. 中间试用了 `undetected-chromedriver` 3.5.5，自带的 chromedriver 二进制对
   Chrome 147 报 `SessionNotCreatedException: only supports Chrome 148`，
   完全启动不了。

## 考虑过的方案

### 方案 A：继续修 Selenium + 手写反检测
- ⛔ 反爬升级速度快过我能维护的速度
- ⛔ 即使过了静态指纹检测，BOSS 还会用 mouse-movement entropy 之类的动态检测
- ⛔ Selenium 4.x 协议变化时也是个迁移痛点

### 方案 B：用 `undetected-chromedriver`
- ⛔ 作者已停止维护（最新 3.5.5 发布于 2024-02）
- ⛔ 对 Chrome 147+ 协议不兼容
- ⛔ 在新 Chrome 上 import 即崩

### 方案 C：用 `nodriver`（采纳）
- ✅ uc 原作者的官方继任，2025-11 还在更新（0.48.1）
- ✅ 直接走 Chrome DevTools Protocol，**没有 chromedriver 中间层**
- ✅ "chromedriver 版本对不齐"这一整类 bug 结构上不可能发生
- ✅ 自带文本搜索（`tab.find("微信")` + best_match）和 XPath retry，selector
  逻辑简化一档

### 方案 D：Playwright
- ⚠️ 是个合理选项，但它对反反爬不如 nodriver 主动
- ⚠️ 安装重，要单独 `playwright install` 拉 130MB 的 browser binary

## 决策

**用 nodriver**。

## 代价 / 限制

1. **async-only API**。项目其它部分都是 sync 流程（`main.py`、
   `write_response.py` 主循环），需要 sync facade + 共享 `uc.loop()` 桥接。
   见 [架构总览](../architecture.md) 的"sync facade + async impl"。
2. **Chromium 系限定**。Edge / Safari 路径在迁移中被丢弃了 —— 那条线本来也没人
   认真用过。
3. **`new_window=True` 是必须的**。持久化 profile 启动时 Chrome 会恢复上次的
   tab，控制 tab 容易被淹没。开新窗口能保证 caller 总是能拿到那个 tab 的引用。
   见 commit [`7dbdf37`](https://github.com/longsizhuo/BossZhiPin_Job_Search/commit/7dbdf37)。
4. **某些 nodriver API 的 timeout 行为不可靠**。比如 `tab.select(sel, timeout=0)`
   会无限阻塞而不是立即返回（见 commit
   [`cde78b2`](https://github.com/longsizhuo/BossZhiPin_Job_Search/commit/cde78b2)）。
   我们的 `_xpath_safe` 包了 `asyncio.wait_for` 兜底。

## 验证

迁移后实际跑：

- ✅ Chrome 147 上启动成功（uc 路径会闪退）
- ✅ 持久化 profile + 一次扫码后续不再触发反爬
- ✅ JD 读取 / 招呼语发送 / 退回列表 全链路通

## 后续

- 升级到 0.49+ 时再 review 一次有没有更稳的 timeout API
- 如果 BOSS 升级反爬到能识别 CDP 客户端的程度，预备方案是用 `remote-debugging-port`
  attach 到用户手动起的真 Chrome（不依赖任何自动化协议）
