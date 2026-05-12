"""把 BOSS 推荐 feed 当前真实状态 dump 到磁盘，用于排查 xpath / 选择器失效。

何时用：
    [website_oper/finding_jobs.py](../website_oper/finding_jobs.py) 抓不到岗位卡
    （日志里看到 ``没找到列表第 N 个岗位（xpath: ...）``）的时候。BOSS 偶尔
    会改前端 DOM，绝对 xpath 会失效。

跑一次：

.. code-block:: bash

    uv run scripts/dump_boss_page.py
    # 或者用其他 profile / URL
    BOSS_CHROME_PROFILE=/path/to/profile uv run scripts/dump_boss_page.py

会落盘 3 个文件到 ``./logs/debug/``：

- ``page.html``       —— 整页 ``outerHTML`` 快照，离线慢慢翻
- ``page.png``        —— 视觉截图，确认 nodriver 看到的就是你想看的
- ``selectors.json``  —— 自动探测的候选岗位列表选择器（带 ``data-*`` 属性的
                          元素、class 含关键词的元素、有 ≥3 个同 tag 同 class
                          子元素的容器）

把这三个文件发给 maintainer 就能定位新选择器，不用一来一回试 DevTools。

跟 [finding_jobs.py](../website_oper/finding_jobs.py) 共用 ``./chrome_profile/``
登录态，所以只要主流程能登录就能跑这个。
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import nodriver as uc
from nodriver import Config

CHROME_PROFILE_DIR = os.path.abspath(
    os.environ.get("BOSS_CHROME_PROFILE", "./chrome_profile")
)
DEBUG_DIR = Path(os.environ.get("BOSS_DEBUG_DIR", "./logs/debug"))
TARGET_URL = os.environ.get(
    "BOSS_DEBUG_URL",
    "https://www.zhipin.com/web/geek/job-recommend?ka=header-job-recommend",
)
SETTLE_SECONDS = float(os.environ.get("BOSS_DEBUG_SETTLE", "8"))

# 探测 JS：尽量穷举 BOSS 可能用的选择器范式。
# 这里**故意手动 JSON.stringify** —— nodriver 0.48 的 ``tab.evaluate`` 即使带
# ``return_by_value=True`` 也偶尔返回 ``RemoteObject``（CDP wrapper）而不是
# Python 原生 dict，Python 侧 json.dumps 直接抛 ``Object of type RemoteObject
# is not JSON serializable``。让 JS 自己输出字符串，Python 拿到再 json.loads，
# 绕开 nodriver 的 marshalling 差异。
PROBE_JS = r"""
JSON.stringify((() => {
  const out = { url: location.href, title: document.title };

  // 1. 总体元素统计
  out.totals = {
    total: document.querySelectorAll("*").length,
    li: document.querySelectorAll("li").length,
    iframes: document.querySelectorAll("iframe").length,
    body_children: document.body.children.length,
  };

  // 2. 带 data-* 属性的候选 —— BOSS 现代版常用 data-jobid / data-securityid 挂数据
  const dataAttrs = [
    "data-jobid", "data-securityid", "data-itemid",
    "data-id", "data-uid", "data-lid", "data-job-id",
  ];
  out.by_data_attr = {};
  for (const attr of dataAttrs) {
    const els = document.querySelectorAll("[" + attr + "]");
    if (els.length === 0) continue;
    out.by_data_attr[attr] = {
      count: els.length,
      sample: Array.from(els).slice(0, 3).map((e) => ({
        tag: e.tagName,
        class: (e.className || "").slice(0, 100),
        text: (e.textContent || "").slice(0, 80).trim().replace(/\s+/g, " "),
      })),
    };
  }

  // 3. class 名含关键词的候选
  const keywords = ["job", "card", "recommend", "item", "list", "pos"];
  out.by_class_keyword = {};
  for (const kw of keywords) {
    const els = document.querySelectorAll('[class*="' + kw + '"]');
    if (els.length === 0) continue;
    const uniqueClasses = [...new Set(
      Array.from(els).slice(0, 100).map((e) => e.className)
    )].slice(0, 8);
    out.by_class_keyword[kw] = {
      count: els.length,
      unique_classes: uniqueClasses,
    };
  }

  // 4. "列表容器"探测 —— 有 ≥3 个同 tag 同 class 子元素的 div
  const candidates = [];
  document.querySelectorAll("*").forEach((el) => {
    const cnt = el.children.length;
    if (cnt < 3) return;
    const firstTag = el.children[0].tagName;
    const firstClass = el.children[0].className;
    if (!firstClass) return; // 跳过没 class 的，太多噪音
    let same = true;
    for (let i = 1; i < cnt; i++) {
      if (el.children[i].tagName !== firstTag || el.children[i].className !== firstClass) {
        same = false;
        break;
      }
    }
    if (!same) return;
    candidates.push({
      parent_tag: el.tagName,
      parent_class: (el.className || "").slice(0, 100),
      child_tag: firstTag,
      child_class: firstClass.slice(0, 100),
      child_count: cnt,
    });
  });
  out.candidate_lists = candidates.slice(0, 15);

  // 5. iframe 列表（如果有，得切 context）
  out.iframe_list = Array.from(document.querySelectorAll("iframe")).map((f) => ({
    src: f.src,
    name: f.name,
    id: f.id,
  }));

  return out;
})())
"""


async def main() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)

    print(f"[启动] Chrome profile: {CHROME_PROFILE_DIR}")
    config = Config()
    config.user_data_dir = CHROME_PROFILE_DIR
    config.headless = False
    browser = await uc.start(config=config)
    tab = await browser.get(TARGET_URL, new_window=True)
    try:
        await tab.activate()
        await tab.bring_to_front()
    except Exception:
        pass

    print(f"[等待] {SETTLE_SECONDS}s 让 BOSS 渲染完...")
    await asyncio.sleep(SETTLE_SECONDS)
    print(f"[当前] URL: {tab.url}")

    if "/web/user/" in tab.url or "passport-zp" in tab.url:
        print(
            "[⚠️] 当前在登录页，profile 没有有效 cookie。先跑一次 "
            "`uv run main.py` 扫码登录，再回来跑这个脚本。"
        )
        browser.stop()
        return

    # 1) outerHTML 快照
    html_path = DEBUG_DIR / "page.html"
    print(f"[1/3] outerHTML → {html_path}")
    try:
        html = await tab.evaluate(
            "document.documentElement.outerHTML",
            return_by_value=True,
        )
    except TypeError:
        # 某些 nodriver 版本签名不一样，回退
        html = await tab.evaluate("document.documentElement.outerHTML")
    html_path.write_text(str(html or ""), encoding="utf-8")
    print(f"      写入 {len(str(html or ''))} 字符")

    # 2) 截图
    png_path = DEBUG_DIR / "page.png"
    print(f"[2/3] 截图 → {png_path}")
    try:
        await tab.save_screenshot(filename=str(png_path))
        print(f"      OK")
    except Exception as e:
        print(f"      失败：{type(e).__name__}: {e}")

    # 3) 选择器探测 —— JS 自己 JSON.stringify，Python 直接拿字符串再 loads。
    # 绕开 nodriver tab.evaluate 在不同版本下对复杂对象的 marshalling 差异。
    selectors_path = DEBUG_DIR / "selectors.json"
    print(f"[3/3] 候选选择器探测 → {selectors_path}")
    raw = await tab.evaluate(PROBE_JS)
    # 某些 nodriver 版本返回 (value, exception_details) tuple，展开
    if isinstance(raw, tuple) and len(raw) >= 1:
        raw = raw[0]
    if isinstance(raw, str):
        try:
            probe = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"      JS 返回不是合法 JSON ({e})，落原文")
            probe = {"raw": raw[:5000], "error": str(e)}
    elif isinstance(raw, dict):
        # 万一未来 nodriver 真的开始 marshal 成 dict 了，也兼容
        probe = raw
    else:
        # 兜底：RemoteObject 或其它，str() 它别炸 json.dumps
        probe = {"raw_repr": repr(raw)[:5000], "type": type(raw).__name__}
    selectors_path.write_text(
        json.dumps(probe, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("=== 完成 ===")
    print(f"3 个文件已写到 {DEBUG_DIR.resolve()}")
    print()
    print("快速看一眼：")
    print(f"  cat {selectors_path} | jq '.totals,.by_data_attr,.by_class_keyword'")
    print(f"  open {png_path}")
    print()
    print("Chrome 窗口会留着，关掉之前不会影响这次 dump 结果。")


if __name__ == "__main__":
    uc.loop().run_until_complete(main())
