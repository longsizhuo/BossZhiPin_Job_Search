"""probe: 定位"抓到的 JD 是反爬垃圾而非正文"的问题，一次性对比多种抽取打法。

背景：``finding_jobs.get_job_description_by_index`` 抓 ``.job-detail-body`` 的
``textContent``，结果把 BOSS 塞进去的 ``<style>`` 块源码 + width:0.1px 的隐藏 span
一起读了，真正的"岗位职责/要求"正文反而被淹没 → 关键词全不命中。

这个脚本点开第 1 个岗位，对同一节点测 4 种抽取法 + 列候选选择器 + dump 一段
outerHTML，好让我们看清哪种能拿到干净正文、该用哪个选择器。**不改主链路。**

跑法（复用桌面 App 已登录的 profile，先把 App 关掉再跑，避免 profile 被占）：

    BOSS_CHROME_PROFILE="$HOME/Library/Application Support/com.longsizhuo.boss-zhipin/chrome_profile" \
        uv run python scripts/probe_jd_extract.py

或用 repo 本地 profile（会要你重新扫码登录一次）：

    uv run python scripts/probe_jd_extract.py
"""
import asyncio
import json

import nodriver as uc
from nodriver import Config

from boss_zhipin.cli import RECOMMEND_URL
from boss_zhipin.website_oper.finding_jobs import CHROME_PROFILE_DIR

# 同一个 .job-detail-body 节点上对比 4 种抽取；并列候选选择器；dump 结构。
DUMP_JS = r"""
JSON.stringify((() => {
  const out = {};
  const el = document.querySelector('.job-detail-body');
  if (!el) { out.found = false; return out; }
  out.found = true;

  const clip = (s, n) => (s || '').replace(/\s+/g, ' ').trim().slice(0, n);

  // 1) 现状：textContent（会带 <style>/<script> 源码 + 隐藏 span）
  out.s1_textContent = { len: (el.textContent || '').trim().length,
                         head: clip(el.textContent, 400) };

  // 2) innerText（浏览器渲染的可见文本，自动排除 <style>/<script> 和 display:none）
  out.s2_innerText = { len: (el.innerText || '').trim().length,
                       head: clip(el.innerText, 400) };

  // 3) TreeWalker：只收"可见"文本节点——跳过 STYLE/SCRIPT、display:none/visibility:hidden、
  //    以及尺寸 < 2px 的反爬隐藏元素。这是最干净的金标准。
  function visibleText(root) {
    let s = '';
    const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(t) {
        let p = t.parentElement;
        while (p && p !== root.parentElement) {
          const tag = p.tagName;
          if (tag === 'STYLE' || tag === 'SCRIPT') return NodeFilter.FILTER_REJECT;
          const cs = getComputedStyle(p);
          if (cs.display === 'none' || cs.visibility === 'hidden') return NodeFilter.FILTER_REJECT;
          const r = p.getBoundingClientRect();
          if (r.width < 2 || r.height < 2) return NodeFilter.FILTER_REJECT;
          p = p.parentElement;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    let n; while ((n = walk.nextNode())) s += n.nodeValue;
    return s;
  }
  const vis = visibleText(el);
  out.s3_visibleText = { len: vis.trim().length, head: clip(vis, 400) };

  // 4) clone 后删 style/script 再 textContent（看是否只 <style> 在捣乱）
  const c = el.cloneNode(true);
  c.querySelectorAll('style,script').forEach(n => n.remove());
  out.s4_clone_nostyle = { len: (c.textContent || '').trim().length,
                           head: clip(c.textContent, 400) };

  // 候选选择器一览：谁的可见文本更像"正文"
  const cands = ['.job-detail-body', '.job-sec-text', '.job-detail', '.job-sec',
                 '[class*=job-detail]', '[class*=job-sec]', '.detail-content'];
  out.candidates = cands.map(sel => {
    const e = document.querySelector(sel);
    return { sel, exists: !!e,
             innerText_len: e ? (e.innerText || '').trim().length : 0,
             innerText_head: e ? clip(e.innerText, 140) : '' };
  });

  // 节点里有几个 <style>/隐藏 span（佐证反爬手法）
  out.style_tags = el.querySelectorAll('style').length;
  out.outerHTML_head = (el.outerHTML || '').slice(0, 900);
  return out;
})())
"""


async def main() -> int:
    cfg = Config()
    cfg.user_data_dir = CHROME_PROFILE_DIR
    cfg.headless = False
    print(f"==> profile: {CHROME_PROFILE_DIR}")
    browser = await uc.start(config=cfg)
    tab = await browser.get(RECOMMEND_URL, new_window=True)

    print("==> 等页面加载 + 卡片出现…（没登录会卡在登录页，先用 App 登录过的 profile）")
    await asyncio.sleep(6)

    clicked = await tab.evaluate(
        "(() => { const c = document.querySelectorAll('.job-card-box');"
        " if (c[0]) { c[0].click(); return c.length; } return 0; })()",
        await_promise=False,
    )
    print(f"==> 点了第 1 个 .job-card-box（页面共 {clicked} 张卡）")
    await asyncio.sleep(4)

    raw = await tab.evaluate(DUMP_JS, await_promise=False)
    data = json.loads(raw) if isinstance(raw, str) else raw
    print("\n================ JD 抽取对比 ================")
    print(json.dumps(data, ensure_ascii=False, indent=2))

    try:
        browser.stop()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(uc.loop().run_until_complete(main()))
