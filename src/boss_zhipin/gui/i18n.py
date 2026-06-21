"""后端面向用户的报错文案（中 / 英）。

为什么后端也要 i18n：``start_run`` 的 pre-flight 校验和简历上传校验会抛
``ValueError`` / ``RuntimeError``，PyTauri 把它序列化成字符串回到前端，前端直接
展示给用户。前端 UI 已经能切中/英（见 ``tauri-ui/src/lib/i18n.ts``），这些后端
串如果只剩中文，英文用户看到的就是半中半英。

语言取自用户在 Config 选的 ``BOSS_LANG``（``env_io.read_language``）。没设过 →
回退中文（前端会在首次启动时把探测到的默认也落进 .env，所以正常情况下后端能跟
前端一致，见 ``App.tsx``）。

只放**会回传给前端的**用户文案。深层业务日志（浏览器 / LLM / 向量化）不在此处，
那些是运维日志、不是 UI，照旧。变量名 / 函数名用英文，文案值才是中/英。
"""
from __future__ import annotations

_MESSAGES: dict[str, dict[str, str]] = {
    # ---- start_run pre-flight ----
    "err.already_running": {
        "zh": "已经在运行了",
        "en": "Already running",
    },
    "err.need_name": {
        "zh": "请先在「运行」页填写你的名字（招呼语署名用）",
        "en": "Enter your name on the Run page first (used as the greeting signature)",
    },
    "err.need_resume": {
        "zh": "找不到简历 PDF —— 在「运行」页把简历 PDF 拖进来（或在 .env 设 RESUME_PATH）",
        "en": "Resume PDF not found — drag your resume PDF onto the Run page (or set RESUME_PATH in .env)",
    },
    "err.need_ai": {
        "zh": "还没配 AI —— 去「配置」tab 选个服务商（或自定义端点）并填 API key",
        "en": "AI not configured — go to the Config tab, pick a provider (or a custom endpoint) and enter the API key",
    },
    "err.need_model": {
        "zh": "还没填模型（model）—— 去「配置」tab 选个预设会自动填，或手填 LLM_MODEL",
        "en": "No model set — pick a preset in the Config tab to auto-fill, or set LLM_MODEL manually",
    },
    # ---- 简历上传校验（resume_io） ----
    "resume.not_found": {
        "zh": "文件不存在：{src}",
        "en": "File not found: {src}",
    },
    "resume.not_readable_pdf": {
        "zh": "不是一个能读取的 PDF（需要 .pdf 且至少一页）",
        "en": "Not a readable PDF (must be .pdf with at least one page)",
    },
    "resume.not_pdf": {
        "zh": "不是一个 PDF 文件（需要 .pdf）",
        "en": "Not a PDF file (must be .pdf)",
    },
    "resume.empty": {
        "zh": "文件是空的",
        "en": "File is empty",
    },
}

_DEFAULT_LANG = "zh"


def _current_lang() -> str:
    """当前 UI 语言：读 BOSS_LANG，未知 / 未设回退中文。

    局部 import env_io 避免 import 环（env_io 不依赖本模块，但保持单向清晰）。
    """
    from boss_zhipin.gui.env_io import read_language

    lang = read_language()
    return lang if lang in ("zh", "en") else _DEFAULT_LANG


def msg(key: str, **vars: object) -> str:
    """取一条本地化文案；``{name}`` 占位符用 kwargs 替换。

    缺 key / 缺当前语言 → 回退中文，再回退 key 本身（开发期一眼看出漏翻）。
    """
    entry = _MESSAGES.get(key, {})
    text = entry.get(_current_lang()) or entry.get(_DEFAULT_LANG) or key
    if vars:
        for k, v in vars.items():
            text = text.replace("{" + k + "}", str(v))
    return text
