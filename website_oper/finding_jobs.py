"""nodriver-backed BOSS automation.

整个模块对外**全部是 async 函数**。调用方（``write_response.py`` 主循环）
也必须 async，并由 ``main.py`` 用 ``uc.loop().run_until_complete(...)`` **整段
跑在一个事件循环里**。

为什么这么设计：之前对外是 sync facade（每个公开函数内部 ``_run`` 调一次
``uc.loop().run_until_complete``），结果每次 enter/exit 事件循环都让 nodriver
的 CDP websocket 进入半死状态，下一次 evaluate 直接 hang 到 timeout。
``scripts/probe_click_card.py`` 单 coroutine 跑同样的 evaluate 是秒返回，
证实就是 sync facade 模式跟 nodriver 的活跃性需求不兼容。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

import nodriver as uc
from nodriver import Config

log = logging.getLogger(__name__)

# 持久化 Chrome profile：第一次手动扫码后 cookie 会留下，之后跑就跳过登录。
# 可用 BOSS_CHROME_PROFILE 环境变量覆盖路径。
CHROME_PROFILE_DIR = os.path.abspath(
    os.environ.get("BOSS_CHROME_PROFILE", "./chrome_profile")
)

_browser: uc.Browser | None = None
_tab: uc.Tab | None = None


def get_tab() -> uc.Tab | None:
    """同步读当前控制的 Tab 引用。仅用作内省。"""
    return _tab


def get_driver():
    raise RuntimeError(
        "get_driver() 已移除：项目已迁到 nodriver，没有 Selenium driver。"
        "请改用 finding_jobs 里的 async helper（get_text_by_css/click_by_xpath/"
        "wait_for_css/send_chat_message/navigate_back）。"
    )


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


# ---------- 浏览器生命周期 ----------


async def shutdown() -> None:
    """关 Chrome 并清空模块级 ``_browser`` / ``_tab``。

    给 GUI 用——用户点"重置"想从头来一遍时调一次，否则下次
    ``open_browser_with_options`` 会留旧 Chrome 进程。CLI 不需要：``main.py``
    退出时 OS 会清理子进程。

    ``Browser.stop()`` 是同步函数，但本函数声明 ``async`` 是为了让 GUI
    runner 能 ``await shutdown()``（runner 一律 await，sync/async 不混用）。

    重启注意：这只关 Chrome 进程；nodriver 跟 uvloop 的重启不兼容问题需要
    GUI 入口传 ``loop="asyncio"`` 才能彻底解决（见 project memory）。
    """
    global _browser, _tab
    if _browser is not None:
        try:
            _browser.stop()
        except Exception as e:
            log.warning("browser.stop() 失败（不致命）: %s", e)
    _browser = None
    _tab = None


async def open_browser_with_options(url: str, browser: str) -> None:
    """启动 Chrome 并打开 url。``browser`` 仅接受 ``"chrome"``。"""
    global _browser, _tab
    if browser != "chrome":
        raise NotImplementedError(
            f"browser={browser!r} 不再支持；nodriver 只走 Chrome。"
        )
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
        log.warning("激活控制 tab 失败（%s），不影响后续操作", e)

    log.info("页面加载中... 当前URL: %s", _tab.url)
    stable_url = await _wait_url_stable(stable_for=2.0, timeout=30)
    log.info("页面已稳定，当前URL: %s", stable_url)


async def log_in() -> None:
    """识别登录状态；未登录则点开微信扫码，等用户扫码登录。"""
    if await _is_logged_in():
        log.info("检测到已登录（profile: %s），跳过扫码", CHROME_PROFILE_DIR)
        return

    cur_url = _tab.url
    log.info("log_in 入口 URL: %s", cur_url)

    if not _on_login_page(cur_url):
        try:
            login_btn = await _tab.find("登录", best_match=True, timeout=15)
            if login_btn:
                await login_btn.click()
                log.info("已点击 header 登录入口")
                await _wait_url_stable(stable_for=2.0, timeout=15)
        except Exception as e:
            log.warning("找不到 header 登录入口（%s），尝试直接在当前页找微信入口", e)

    try:
        wechat_btn = await _tab.find("微信", best_match=True, timeout=10)
        if wechat_btn:
            await wechat_btn.click()
            log.info("已点击微信登录入口，请扫码...")
        else:
            log.warning("未自动点上微信入口，请在浏览器里手动选择登录方式")
    except Exception as e:
        log.warning("查找微信入口出错（%s），请手动选择登录方式", e)

    log.info("等待扫码登录... (最多 300 秒)")
    deadline = asyncio.get_event_loop().time() + 300
    while asyncio.get_event_loop().time() < deadline:
        if await _is_logged_in():
            log.info("登录成功！cookie 已写入 profile，下次跑应该不用再扫")
            return
        await asyncio.sleep(2)
    log.warning("登录超时，请确认是否已扫码登录")


# ---------- JS 评估辅助 ----------


async def _safe_evaluate(js: str, timeout: float = 10) -> dict:
    """跑 ``tab.evaluate(js)``，期望 JS 自己 ``JSON.stringify`` 返回字符串。

    自带 ``asyncio.wait_for`` 兜底 + JSON 解析容错 —— 永远不抛、永远返回 dict
    （失败时空 dict）。
    """
    js_head = js.strip()[:80].replace("\n", " ")
    try:
        raw = await asyncio.wait_for(_tab.evaluate(js), timeout=timeout)
    except asyncio.TimeoutError:
        log.warning("evaluate 超过 %ss 没返回（JS: %s...）", timeout, js_head)
        return {}
    except Exception as e:
        log.warning("evaluate 抛 %s: %s（JS: %s...）", type(e).__name__, e, js_head)
        return {}
    if isinstance(raw, tuple):
        raw = raw[0]
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            log.warning("JS 返回不是合法 JSON：%s（前 200 字符：%r）", e, raw[:200])
            return {}
    if isinstance(raw, dict):
        return raw
    log.warning("evaluate 返回类型 %s（不是 str/dict）：%r", type(raw).__name__, repr(raw)[:200])
    return {}


async def _js_click_at_index(css_selector: str, index_1: int) -> dict:
    """在 JS 里点 ``css_selector`` 命中的第 N 个元素（1-indexed）。"""
    js = f"""
    JSON.stringify((() => {{
      try {{
        const els = document.querySelectorAll({json.dumps(css_selector)});
        if (els.length < {index_1}) return {{ok: false, total: els.length}};
        els[{index_1 - 1}].click();
        return {{ok: true, total: els.length}};
      }} catch (e) {{
        return {{ok: false, error: String(e), stack: e.stack || ''}};
      }}
    }})())
    """
    return await _safe_evaluate(js)


async def _js_wait_text(css_selector: str, min_len: int, timeout_s: float) -> str | None:
    """轮询直到 ``css_selector`` 命中且 ``text.length >= min_len``，返回 text；超时返回 None。"""
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        js = f"""
        JSON.stringify((() => {{
          try {{
            const el = document.querySelector({json.dumps(css_selector)});
            if (!el) return {{ok: false, reason: 'not_found'}};
            const text = (el.textContent || '').trim();
            if (text.length < {min_len}) return {{ok: false, reason: 'too_short', len: text.length}};
            return {{ok: true, text: text}};
          }} catch (e) {{
            return {{ok: false, error: String(e)}};
          }}
        }})())
        """
        result = await _safe_evaluate(js, timeout=5)
        if result.get("ok"):
            return result["text"]
        await asyncio.sleep(0.5)
    return None


async def _xpath_safe(xp: str, timeout: float = 3.0) -> list:
    """``tab.xpath`` 的兜底封装（保留给 ``select_dropdown_option`` 用，主路径已不依赖它）。"""
    try:
        result = await asyncio.wait_for(
            _tab.xpath(xp, timeout=timeout),
            timeout=timeout + 2,
        )
        return result or []
    except asyncio.TimeoutError:
        log.warning("xpath 超时: %s", xp[:80])
        return []
    except Exception as e:
        log.warning("xpath 出错: %s: %s", type(e).__name__, e)
        return []


# ---------- 业务 helper ----------


async def select_dropdown_option(label: str) -> None:
    """空 label 表示用 BOSS 默认推荐 feed，不主动选 tag。"""
    if not label:
        log.info("[select_dropdown_option] label 为空，沿用当前推荐 feed")
        return
    log.info("[select_dropdown_option] label=%r", label)

    log.info("  路径 1: 找推荐 tag chip ...")
    chip_xp = (
        "//*[contains(@class,'recommend-job-btn')"
        " and contains(@class,'has-tooltip')]"
    )
    chips = await _xpath_safe(chip_xp, timeout=3)
    log.info("    找到 %d 个 tag chip", len(chips))
    for el in chips:
        text = (el.text or "").strip()
        if label in text:
            log.info("    → 命中 %r，点击", text)
            await el.click()
            return

    log.info("  路径 2: 找下拉菜单触发器 ...")
    trigger = await _xpath_safe(
        "//*[@id='wrap']/div[2]/div[1]/div/div[1]/div", timeout=3
    )
    if trigger:
        log.info("    → 点开下拉")
        await trigger[0].click()
        await _xpath_safe(
            "//ul[contains(@class,'dropdown-expect-list')]", timeout=3
        )
        options = await _xpath_safe(
            f"//li[contains(text(), '{label}')]", timeout=3
        )
        if options:
            log.info("    → 命中下拉 option %r，点击", label)
            await options[0].click()
            return
        log.info("    下拉里没有 %r", label)
    else:
        log.info("    没找到下拉触发器")

    log.info("  路径 3: fallback —— 用 BOSS 默认的推荐 feed 继续（不主动选 tag）")


async def get_job_description_by_index(index: int) -> str | None:
    """点开第 N 个岗位卡（1-indexed），返回右侧 JD 详情面板的文本；失败返回 None。"""
    log.info("[get_job_description_by_index] index=%d", index)
    # 全程走 tab.evaluate(JS)，CSS selector + 浏览器内 click 都在 JS 里做完。
    click_result = await _js_click_at_index(".job-card-box", index)
    log.info("  点击 .job-card-box[%d]: %s", index, click_result)
    if not click_result.get("ok"):
        return None

    jd = await _js_wait_text(".job-detail-body", min_len=50, timeout_s=10)
    if jd is None:
        log.info("  10s 内 .job-detail-body 没出现或文本太短")
        return None
    log.info("  JD 长度 %d 字符", len(jd))
    return jd


async def get_text_by_css(selector: str, timeout: float = 5) -> str | None:
    """通用：返回 CSS 选择器命中元素的 text，找不到返回 None。"""
    try:
        el = await _tab.select(selector, timeout=timeout)
    except Exception:
        return None
    return el.text if el else None


async def click_by_xpath(xpath: str, timeout: float = 10) -> bool:
    """通过 xpath 找到元素并点击。成功返回 True。"""
    els = await _xpath_safe(xpath, timeout=timeout)
    if not els:
        return False
    await els[0].click()
    return True


async def wait_for_css(selector: str, timeout: float = 50) -> bool:
    """等 CSS 选择器命中。成功返回 True，超时返回 False。"""
    try:
        el = await _tab.select(selector, timeout=timeout)
    except Exception:
        return False
    return el is not None


async def send_chat_message(text: str) -> None:
    """把 text 打进 ``#chat-input`` 然后回车发送。"""
    chat = await _tab.select("#chat-input", timeout=10)
    if not chat:
        raise RuntimeError("chat input (#chat-input) 未找到")
    await chat.send_keys(text)
    await asyncio.sleep(3)
    await chat.send_keys("\n")
    await asyncio.sleep(1)


async def navigate_back() -> None:
    """``history.back()`` —— 浏览器返回上一页。"""
    await _tab.evaluate("history.back()")
    await asyncio.sleep(3)


# Variables（保持向后兼容）
url = "https://www.zhipin.com/web/geek/job-recommend?ka=header-job-recommend"
browser_type = "chrome"
