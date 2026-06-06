# Wiki 总入口

## 主题文档

- [架构总览](architecture.md) —— 数据流、模块边界、关键抽象
- [常见故障排查](troubleshooting.md) —— Chrome 闪退 / 反爬触发 / 卡登录页 等
- [FAQ](faq.md) —— 跟使用 / 选 provider / 调 prompt 相关的常见问题
- [Debugging Playbook](debugging-playbook.md) —— 难 bug 怎么查（agent 视角 + 指挥方视角）
- [Postmortem 2026-05-13: CDP hang](postmortem-2026-05-13-cdp-hang.md) —— sync facade 跟 nodriver CDP 不兼容那次 bug 的完整复盘

## Architecture Decision Records (ADR)

记录"为什么这么做"和"考虑过什么但没采纳"。读 ADR 比读 commit message 更快搞清
楚一个设计的来龙去脉。

- [ADR-001 用 nodriver 替代 Selenium / undetected-chromedriver](adr/001-nodriver-over-selenium.md)
- [ADR-002 三家 LLM provider 共用 OpenAI SDK](adr/002-three-providers.md)
- [ADR-003 LLM telemetry 单独落盘，跟 letters audit log 分离](adr/003-telemetry-separate.md)
- [ADR-004 持久化 Chrome profile 而不是 mock 登录态](adr/004-persistent-chrome-profile.md)

## 怎么继续读

- 第一次看本项目 → `architecture.md`
- 跑起来卡住 → `troubleshooting.md`
- 想动代码前 → 主目录 [CLAUDE.md](../../CLAUDE.md) + [CONTRIBUTING.md](../../CONTRIBUTING.md)
- 觉得某个设计奇怪 → 对应 ADR
