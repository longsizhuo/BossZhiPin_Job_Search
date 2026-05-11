"""nodriver-backed BOSS automation.

整个模块对外暴露同步 API，内部把所有浏览器调用 await 进一个共享的事件循环
（nodriver 推荐的 ``uc.loop()``）。这样 [write_response.py](write_response.py) 等
sync 调用方不需要全部改成 async，只需要换调用名。
"""

import asyncio
import os

import nodriver as uc
from nodriver import Config

# 持久化 Chrome profile：第一次手动扫码后 cookie 会留下，之后跑就跳过登录。
# 可用 BOSS_CHROME_PROFILE 环境变量覆盖路径。
CHROME_PROFILE_DIR = os.path.abspath(
    os.environ.get("BOSS_CHROME_PROFILE", "./chrome_profile")
)

_browser: uc.Browser | None = None
_tab: uc.Tab | None = None


def _run(coro):
    return uc.loop().run_until_complete(coro)


def get_tab() -> uc.Tab | None:
    return _tab


def _on_login_page(url: str) -> bool:
    return any(s in url for s in ("/web/user/", "passport-zp", "/login"))


async def _is_logged_in() -> bool:
    """登录态以 URL 为准：BOSS 未登录时一定 redirect 到 /web/user/ 类路径。"""
    if _tab is None:
        return False
    return not _on_login_page(_tab.url)


async def _wait_url_stable(stable_for: float = 2.0, timeout: float = 30) -> str:
    """等到 tab.url 连续 stable_for 秒不变，避开 BOSS 登录页的重定向抖动。"""
    end = asyncio.get_event_loop().time() + timeout
    last_url = _tab.url
    last_change = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() < end:
        cur = _tab.url
        now = asyncio.get_event_loop().time()
        if cur != last_url:
            last_url = cur
            last_change = now
        elif now - last_change >= stable_for:
            return cur
        await asyncio.sleep(0.2)
    return last_url


async def _open_browser_impl(url: str) -> None:
    global _browser, _tab
    os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)
    config = Config()
    config.user_data_dir = CHROME_PROFILE_DIR
    config.headless = False
    _browser = await uc.start(config=config)

    # 持久化 profile 启动时 Chrome 会把上次的 tab 都恢复出来；脚本控制的 tab
    # 直接放到一个独立的新窗口里，跟历史窗口井水不犯河水，新窗口默认抢焦。
    _tab = await _browser.get(url, new_window=True)
    try:
        await _tab.activate()
        await _tab.bring_to_front()
    except Exception as e:
        print(f"激活控制 tab 失败（{e}），不影响后续操作")

    print(f"页面加载中... 当前URL: {_tab.url}")
    stable_url = await _wait_url_stable(stable_for=2.0, timeout=30)
    print(f"页面已稳定，当前URL: {stable_url}")


def open_browser_with_options(url: str, browser: str) -> None:
    """启动 Chrome 并打开 url。``browser`` 仅接受 'chrome'（nodriver 不支持 Edge/Safari）。"""
    if browser != "chrome":
        raise NotImplementedError(
            f"browser={browser!r} 不再支持；nodriver 只走 Chrome。"
        )
    _run(_open_browser_impl(url))


async def _log_in_impl() -> None:
    if await _is_logged_in():
        print(f"检测到已登录（profile: {CHROME_PROFILE_DIR}），跳过扫码")
        return

    cur_url = _tab.url
    print(f"log_in 入口 URL: {cur_url}")

    if not _on_login_page(cur_url):
        try:
            login_btn = await _tab.find("登录", best_match=True, timeout=15)
            if login_btn:
                await login_btn.click()
                print("已点击 header 登录入口")
                await _wait_url_stable(stable_for=2.0, timeout=15)
        except Exception as e:
            print(f"找不到 header 登录入口（{e}），尝试直接在当前页找微信入口")

    try:
        wechat_btn = await _tab.find("微信", best_match=True, timeout=10)
        if wechat_btn:
            await wechat_btn.click()
            print("已点击微信登录入口，请扫码...")
        else:
            print("未自动点上微信入口，请在浏览器里手动选择登录方式")
    except Exception as e:
        print(f"查找微信入口出错（{e}），请手动选择登录方式")

    print("等待扫码登录... (最多 300 秒)")
    deadline = asyncio.get_event_loop().time() + 300
    while asyncio.get_event_loop().time() < deadline:
        if await _is_logged_in():
            print("登录成功！cookie 已写入 profile，下次跑应该不用再扫")
            return
        await asyncio.sleep(2)
    print("登录超时，请确认是否已扫码登录")


def log_in() -> None:
    _run(_log_in_impl())


async def _xpath_safe(xp: str, timeout: float = 3.0) -> list:
    """xpath + 硬超时兜底，nodriver 自己的 timeout 不可靠时不会拖死整个脚本。"""
    try:
        result = await asyncio.wait_for(
            _tab.xpath(xp, timeout=timeout),
            timeout=timeout + 2,
        )
        return result or []
    except asyncio.TimeoutError:
        print(f"  ⏱ xpath 超时: {xp[:80]}")
        return []
    except Exception as e:
        print(f"  ✗ xpath 出错: {type(e).__name__}: {e}")
        return []


async def _select_dropdown_option_impl(label: str) -> None:
    """优先点"推荐岗位 tag" → 下拉菜单 → fallback 默认推荐 feed（不过滤）。"""
    print(f"[select_dropdown_option] label={label!r}")

    print("  路径 1: 找推荐 tag chip ...")
    chip_xp = (
        "//*[contains(@class,'recommend-job-btn')"
        " and contains(@class,'has-tooltip')]"
    )
    chips = await _xpath_safe(chip_xp, timeout=3)
    print(f"    找到 {len(chips)} 个 tag chip")
    for el in chips:
        text = (el.text or "").strip()
        if label in text:
            print(f"    → 命中 '{text}'，点击")
            await el.click()
            return

    print("  路径 2: 找下拉菜单触发器 ...")
    trigger = await _xpath_safe(
        "//*[@id='wrap']/div[2]/div[1]/div/div[1]/div", timeout=3
    )
    if trigger:
        print("    → 点开下拉")
        await trigger[0].click()
        # 等下拉容器出现再查 option
        await _xpath_safe(
            "//ul[contains(@class,'dropdown-expect-list')]", timeout=3
        )
        options = await _xpath_safe(
            f"//li[contains(text(), '{label}')]", timeout=3
        )
        if options:
            print(f"    → 命中下拉 option '{label}'，点击")
            await options[0].click()
            return
        print(f"    下拉里没有 '{label}'")
    else:
        print("    没找到下拉触发器")

    print(f"  路径 3: fallback —— 用 BOSS 默认的推荐 feed 继续（不主动选 tag）")


def select_dropdown_option(label: str) -> None:
    """空 label 表示用 BOSS 默认推荐 feed，不主动选 tag。"""
    if not label:
        print("[select_dropdown_option] label 为空，沿用当前推荐 feed")
        return
    _run(_select_dropdown_option_impl(label))


async def _get_job_description_by_index_impl(index: int) -> str | None:
    print(f"[get_job_description_by_index] index={index}")
    job_xpath = f"//*[@id='wrap']/div[2]/div[2]/div/div/div[1]/ul/li[{index}]"
    jobs = await _xpath_safe(job_xpath, timeout=5)
    if not jobs:
        print(f"  没找到列表第 {index} 个岗位（xpath: {job_xpath}）")
        return None
    print(f"  点击列表第 {index} 个岗位")
    await jobs[0].click()

    desc_xpath = "//*[@id='wrap']/div[2]/div[2]/div/div/div[2]/div/div[2]/p"
    descs = await _xpath_safe(desc_xpath, timeout=10)
    if not descs:
        print(f"  点击后 10s 内没读到 JD（xpath: {desc_xpath}）")
        return None
    jd = descs[0].text or ""
    print(f"  JD 长度 {len(jd)} 字符")
    return jd


def get_job_description_by_index(index: int) -> str | None:
    return _run(_get_job_description_by_index_impl(index))


async def _get_text_by_css_impl(selector: str, timeout: float) -> str | None:
    try:
        el = await _tab.select(selector, timeout=timeout)
    except Exception:
        return None
    return el.text if el else None


def get_text_by_css(selector: str, timeout: float = 5) -> str | None:
    """通用：返回 CSS 选择器命中元素的 text，找不到返回 None。"""
    return _run(_get_text_by_css_impl(selector, timeout))


async def _click_by_xpath_impl(xpath: str, timeout: float) -> bool:
    els = await _tab.xpath(xpath, timeout=timeout)
    if not els:
        return False
    await els[0].click()
    return True


def click_by_xpath(xpath: str, timeout: float = 10) -> bool:
    return _run(_click_by_xpath_impl(xpath, timeout))


async def _wait_for_css_impl(selector: str, timeout: float) -> bool:
    try:
        el = await _tab.select(selector, timeout=timeout)
    except Exception:
        return False
    return el is not None


def wait_for_css(selector: str, timeout: float = 50) -> bool:
    return _run(_wait_for_css_impl(selector, timeout))


async def _send_chat_message_impl(text: str) -> None:
    """把 text 打进 #chat-input 然后回车发送。"""
    chat = await _tab.select("#chat-input", timeout=10)
    if not chat:
        raise RuntimeError("chat input (#chat-input) 未找到")
    await chat.send_keys(text)
    await asyncio.sleep(3)
    await chat.send_keys("\n")
    await asyncio.sleep(1)


def send_chat_message(text: str) -> None:
    _run(_send_chat_message_impl(text))


async def _navigate_back_impl() -> None:
    await _tab.evaluate("history.back()")
    await asyncio.sleep(3)


def navigate_back() -> None:
    _run(_navigate_back_impl())


# 兼容旧入口；不再有"driver"对象，调用方应该改用上面的同步辅助函数。
def get_driver():
    raise RuntimeError(
        "get_driver() 已移除：项目已迁到 nodriver，没有 Selenium driver。"
        "请改用 finding_jobs 里同步辅助函数（get_text_by_css/click_by_xpath/"
        "wait_for_css/send_chat_message/navigate_back）。"
    )


# Variables（保持向后兼容）
url = "https://www.zhipin.com/web/geek/job-recommend?ka=header-job-recommend"
browser_type = "chrome"
