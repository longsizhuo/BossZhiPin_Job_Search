# ADR-004：用独立的持久化 Chrome profile 而不是日常 profile / 临时 profile

- **状态**：已采纳
- **日期**：2026-05-11
- **决策人**：longsizhuo
- **相关 commit**：[`eda7af4`](https://github.com/longsizhuo/BossZhiPin_Job_Search/commit/eda7af4)
  + [`7dbdf37`](https://github.com/longsizhuo/BossZhiPin_Job_Search/commit/7dbdf37)

## 背景

BOSS 直聘的反爬识别 Selenium 后会**立即清除登录态 cookie + 强制重定向**。这
意味着 Selenium-driven Chrome 上登录的状态保不住，下次跑还得重新扫码。

需要解决：**怎么让脚本起来时就是已登录状态**。

## 三个选项

### 选项 1：每次跑都临时扫码
- ⛔ 用户体验太差 —— 每次跑都要拿手机扫一次
- ⛔ 短时间内多次扫码可能触发 BOSS 的"账号异地登录"风控

### 选项 2：用用户日常 Chrome profile（`~/Library/.../Chrome/Default`）
- ✅ 用户日常浏览器里如果登过 BOSS，cookie 直接可用
- ⛔ Chrome **同一时刻只允许一个进程占用一个 profile**，意味着用户必须先完全
  退出日常 Chrome 才能跑脚本
- ⛔ 脚本拿到的不只是 BOSS cookie，是用户**所有**网站的 cookie / 扩展 / 浏览
  历史 —— 权限放得太大
- ⛔ 扩展（AdBlock / 翻译 / 密码管理器）干扰自动化点击的概率非平凡
- ⛔ 如果脚本崩了，日常 Chrome 再启动可能弹"Chrome 没正常关闭"

### 选项 3：独立的持久化 profile 目录（采纳）
- ✅ 第一次扫码后 cookie 落盘到 `./chrome_profile/`，**之后跑脚本就跳过登录**
- ✅ 跟用户日常 Chrome 完全隔离，互不干扰
- ✅ 没有扩展干扰
- ✅ 想换账号 / 重置就 `rm -rf chrome_profile/`
- ⚠️ 第一次必须扫码（不可避免）
- ⚠️ 用户视觉上看到的是一个空白 Chrome，可能困惑 "这不是我的 Chrome"

## 决策

用**独立持久化 profile**，默认目录 `./chrome_profile/`，可通过 `BOSS_CHROME_PROFILE`
环境变量覆盖。

代码上对应 [`finding_jobs.py:14`](../../website_oper/finding_jobs.py#L14)：

```python
CHROME_PROFILE_DIR = os.path.abspath(
    os.environ.get("BOSS_CHROME_PROFILE", "./chrome_profile")
)
```

nodriver Config 上：

```python
config = Config()
config.user_data_dir = CHROME_PROFILE_DIR
config.headless = False
_browser = await uc.start(config=config)
```

nodriver 官方文档明确说：**指定了 `user_data_dir` 后，nodriver 退出时不会清理
这个目录**。我们恰好需要这个语义。

## 一个意外坑：恢复 tab

Chrome 用持久化 profile 启动时**会恢复上次会话的所有 tab**。结果：

1. nodriver `browser.get(url)` 默认导航的是"main_tab"
2. main_tab 可能是 chrome://newtab/，也可能是用户上次留的 tab
3. 视觉前台是哪个 tab 不确定，**控制 tab 经常被淹**

试过几个方案：

| 尝试 | 结果 |
|---|---|
| 启动后只 `await tab.bring_to_front()` | ❌ macOS Chrome 偶尔不抢焦 |
| 启动后 close 除控制 tab 之外的所有 tab | ❌ Tab 对象 identity 跨 query 不稳，误关 control tab → Chrome 闪退（commit [`7f95efe`](https://github.com/longsizhuo/BossZhiPin_Job_Search/commit/7f95efe) 翻车记录） |
| `browser.get(url, new_window=True)`（采纳） | ✅ 控制 tab 在独立新窗口，恢复的窗口不动 |

## 代价

1. **磁盘占用**：典型 50-100 MB（Chrome 内部缓存 / Local Storage / Service Worker
   等）。在 `.gitignore` 防止误提交。
2. **跨机器迁移**：如果用户换机器，需要把 `chrome_profile/` 一起拷贝过去。或者
   直接换机器后再扫一次码（推荐）。
3. **profile 锁**：如果两个 `main.py` 实例同时跑，第二个会因为 profile 锁失败。
   单用户单脚本场景下不是问题，但要在 troubleshooting 文档里提一下。

## 验证

实测：

- ✅ 第一次扫码后退出脚本，再跑一次 → 看到 `检测到已登录...，跳过扫码`
- ✅ 跨日重启电脑后 cookie 仍在
- ✅ 用户日常 Chrome 同时打开不冲突

## 后续

- 如果哪天 BOSS 升级反爬到能**主动 invalidate Selenium-driven 浏览器 cookie**，
  这个方案就不够了。预备方案：
  - 用户手动起 Chrome 用 `--remote-debugging-port=9222 --user-data-dir=...`
  - 脚本 attach 到那个端口而不是启动新 Chrome
  - 这样 BOSS 看到的是个真用户起的 Chrome，没有自动化痕迹
- 如果 nodriver 升级支持自动选 main_tab，可能能取消 `new_window=True`
