---
type: reference
title: 变更记录 (Changelog)
tags: [changelog, history]
intent: 变更记录
schema_source: []
documents:
  symbols:
    - _is_logged_in_from_page_state
    - _is_logged_in
---

# 变更记录

本项目的人工变更记录。实现细节以代码 + 对应 ADR / wiki 为准，这里只记
「改了什么 / 为什么 / 影响范围」。文档遵循 [OKF frontmatter](https://github.com/longsizhuo/okf-frontmatter) 约定。

## 2026-06-30 — 修复登录态误判 (PR #29)

### 变更内容
- `src/boss_zhipin/website_oper/finding_jobs.py`：抽出纯函数 `_is_logged_in_from_page_state`，
  在原 `login-wall` 浮层之外，新增「顶部登录按钮」+「正文登录提示文本」两类未登录信号。
- `tests/test_finding_jobs_text.py`：补登录页 URL / 顶部登录入口 / 登录提示文本 / 已登录页面 4 个回归测试。

### 原因
未完整登录的 BOSS 职位页可能停留在职位列表或推荐页，但页面上仍有登录入口或
「登录查看完整内容」提示。原逻辑只看 URL + 单一浮层，容易误判为已登录，跳过扫码后直接抓 JD。

### 影响范围
仅影响浏览器自动化的登录态识别；未改岗位筛选、翻页加载、招呼语发送。所有新信号只向
「判未登录」方向推，故障方向安全（最坏多扫一次码）。

贡献者：@4evour
