"""命令行诊断：打印「复制信息去问 AI」那段求助报告（CLI 版，不依赖 GUI）。

    uv run python -m boss_zhipin.diagnose

用途：源码路径（onboarding skill 的 Path B）用户 / 协作者在终端一行拿到 app 上下文
+ 配置体检（版本、系统、LLM 端点/key/model/简历，**不含 key 明文**），贴给 AI 或自查。
跟 GUI 右上角「🆘 复制Log问AI」按钮同一份生成逻辑（``gui.diagnostics.build_ai_help``）。

CLI 没有 GUI 的实时日志缓冲，所以"最近日志"段是空的——价值在配置/版本/状态体检；
运行日志看终端输出即可。
"""
from __future__ import annotations


def main() -> int:
    # 延迟 import：让没装 GUI 可选依赖时 import 本模块不立即炸（diagnostics 只用
    # 轻量的 env/updates/llm_config/resume_io，不拉 torch）。
    from boss_zhipin.gui.diagnostics import build_ai_help

    print(build_ai_help([]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
