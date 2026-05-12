"""独立诊断脚本：在不动主链路的前提下，测 ``tab.evaluate`` 各种打法在当前
BOSS 页面上**到底哪一种能用**。

为什么需要：主链路 ``_get_job_description_by_index_impl`` 改完一版让 user
重跑一次浪费时间。这个脚本一次性试 4 个阶段，输出告诉我们 evaluate 到底
是健康的、复杂 JS 才崩、还是整个 channel 都死了。

跑：
    uv run scripts/probe_click_card.py

会看到 4 个阶段的诊断：
  1. ``tab.evaluate('1+1')``  —— tab/CDP channel 健不健康
  2. 简单查询  —— 不用 IIFE，直接返回数字
  3. 复杂 IIFE + JSON.stringify  —— 跟主链路一样的 JS pattern
  4. 点击第 1 个岗位卡 + 等 JD  —— 完整动作链路

每个阶段独立 timeout（5s 或 10s），失败的不影响后面继续。Chrome 窗口跑完
不关，方便人工继续 inspect。
"""
from __future__ import annotations

import asyncio
import os

import nodriver as uc
from nodriver import Config

PROFILE = os.path.abspath(os.environ.get("BOSS_CHROME_PROFILE", "./chrome_profile"))
URL = "https://www.zhipin.com/web/geek/job-recommend?ka=header-job-recommend"
SETTLE = float(os.environ.get("BOSS_PROBE_SETTLE", "8"))

# 跟主链路里 _js_click_at_index 用的 JS 完全一致（用 IIFE + JSON.stringify）
CLICK_JS = """
JSON.stringify((() => {
  try {
    const els = document.querySelectorAll('.job-card-box');
    if (!els.length) return {ok: false, reason: 'no_cards'};
    els[0].click();
    return {ok: true, total: els.length};
  } catch (e) {
    return {ok: false, error: String(e)};
  }
})())
"""

CHECK_JS = """
JSON.stringify((() => {
  const detail = document.querySelector('.job-detail-body');
  return {
    url: location.href,
    cards: document.querySelectorAll('.job-card-box').length,
    has_detail: !!detail,
    detail_text_len: (detail?.textContent || '').length,
    detail_preview: (detail?.textContent || '').trim().slice(0, 120)
  };
})())
"""


async def try_eval(label: str, tab, expr: str, timeout: float) -> None:
    """跑一次 ``tab.evaluate``，把类型 + 内容 + 耗时打出来。永远不抛。"""
    print(f"\n[{label}] expr (前 100): {expr.strip()[:100]!r}")
    print(f"  timeout: {timeout}s")
    t0 = asyncio.get_event_loop().time()
    try:
        result = await asyncio.wait_for(tab.evaluate(expr), timeout=timeout)
        dt = asyncio.get_event_loop().time() - t0
        rtype = type(result).__name__
        rrepr = repr(result)[:300]
        print(f"  ✓ {dt:.2f}s | type={rtype} | result={rrepr}")
    except asyncio.TimeoutError:
        dt = asyncio.get_event_loop().time() - t0
        print(f"  ✗ {dt:.2f}s | TIMEOUT")
    except Exception as e:
        dt = asyncio.get_event_loop().time() - t0
        print(f"  ✗ {dt:.2f}s | {type(e).__name__}: {e}")


async def main() -> None:
    print(f"[启动] profile={PROFILE}")
    config = Config()
    config.user_data_dir = PROFILE
    config.headless = False
    browser = await uc.start(config=config)
    tab = await browser.get(URL, new_window=True)
    try:
        await tab.activate()
        await tab.bring_to_front()
    except Exception:
        pass
    print(f"[当前 URL] {tab.url}")
    print(f"[等待] {SETTLE}s 让 Vue mount + 异步接口返回...")
    await asyncio.sleep(SETTLE)
    print(f"[当前 URL] {tab.url}")

    # 阶段 1：最弱信号 —— 1+1
    await try_eval("阶段 1: 1+1", tab, "1+1", timeout=5)

    # 阶段 2：简单查询（直接表达式，不 IIFE）
    await try_eval(
        "阶段 2: 简单 querySelectorAll 计数",
        tab,
        "document.querySelectorAll('.job-card-box').length",
        timeout=5,
    )

    # 阶段 3：复杂 IIFE + JSON.stringify（跟主链路一样）
    await try_eval("阶段 3: 复杂 IIFE 查询", tab, CHECK_JS, timeout=10)

    # 阶段 4：点击第一个卡片
    await try_eval("阶段 4: 点击 .job-card-box[0]", tab, CLICK_JS, timeout=10)

    # 阶段 4 之后等 3s 让 JD 加载，再查一次
    print("\n[等待] 3s 让点击后的 JD 详情面板渲染...")
    await asyncio.sleep(3)
    await try_eval("阶段 5: 点击后再查页面状态", tab, CHECK_JS, timeout=10)

    print("\n=== 诊断完成。结论查表 ===\n")
    print("  阶段 1 也 timeout      → tab/CDP channel 死了，可能是 _tab 引用失效或反爬关 channel")
    print("  阶段 1 ✓ 但阶段 2 ✗   → 跟 querySelectorAll 有关（不太可能，但要排除）")
    print("  阶段 1+2 ✓ 但阶段 3 ✗ → IIFE / JSON.stringify pattern 在这页有问题")
    print("  阶段 1+2+3 ✓ 但 4 ✗   → click 触发了 BOSS 反爬，evaluate 之后挂了")
    print("  全 ✓                  → 主链路的问题是别的（比如调用时 tab 还没 ready）")
    print()
    print("Chrome 窗口不关，方便人工继续 DevTools 测。")


if __name__ == "__main__":
    uc.loop().run_until_complete(main())
