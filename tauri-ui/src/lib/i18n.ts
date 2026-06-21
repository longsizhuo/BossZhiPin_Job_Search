/** UI 文案目录（中 / 英）+ 极简 translate。
 *
 * 为什么自己写而不是上 i18next：整个 App 只有三页、~120 条文案，一个 flat dict +
 * 一个 translate 函数足够，省掉一个运行时依赖 + provider 包裹。
 *
 * 用法：组件里 `const t = useT()`（见 store.ts），`t("run.title")`。带占位符的
 * 文案用 `{name}` 形式，调用时 `t("update.available", { latest, current })`。
 *
 * 约定：
 * - key 用 `page.thing` 命名，方便定位。
 * - 缺 key / 缺某语言时回退到 zh，再回退到 key 本身（开发期一眼看出漏翻）。
 * - 纯品牌串（Boss·Zhipin / 各种 BADGE 如 ERROR / SENT / DRY）不进目录，原样保留。
 * - 语言选择器自己的标签刻意保持双语（见 config.language），避免用户切到看不懂的
 *   语言后找不回来。
 */

export type Lang = "zh" | "en";

export const LANGS: { value: Lang; label: string }[] = [
  { value: "zh", label: "中文" },
  { value: "en", label: "English" },
];

type Dict = Record<string, string>;

const zh: Dict = {
  // ---- App / 顶部导航 ----
  "tab.run": "运行",
  "tab.config": "配置",
  "tab.history": "历史",
  "header.warn1": "另一个 Chrome 窗口正在自动化",
  "header.warn2": "请勿手动关闭",
  "header.askAi": "🆘 复制Log问AI",

  // ---- 「复制信息去问 AI」 ----
  "askai.btn": "复制信息去问 AI",
  "askai.ok": "✓ 已复制 —— 粘贴到 ChatGPT / Claude 等任意 AI，它就能帮你了",
  "askai.fail": "复制失败 —— 请重试，或用「复制日志」",

  // ---- UpdateBanner ----
  "update.available": "新版本 v{latest} 可用 · 当前 v{current}",
  "update.download": "前往下载 ↗",
  "update.dismiss": "关闭提示",

  // ---- 通用按钮 / 徽章 ----
  "btn.save": "保存 →",
  "btn.saving": "保存中...",
  "btn.refresh": "刷新 ↻",
  "btn.pickFile": "选择文件…",
  "btn.start": "开始",
  "btn.stop": "▌ 停止",
  "btn.resetChrome": "重置 Chrome",
  "btn.copyLogs": "复制日志",
  "btn.openIssues": "打开 issues ↗",
  "btn.copyPath": "复制路径",
  "btn.show": "显示",
  "btn.hide": "隐藏",
  "common.loading": "Loading...",

  // ---- Run 页 ----
  "run.title": "运行",
  "run.subtitle": "填表 → 开始 → 看着它打招呼",
  "run.status": "状态",
  "run.statusRunningJob": "运行中 · 当前 job #{index}",
  "run.statusStarting": "运行中 · 启动中",
  "run.statusIdle": "空闲",
  "run.fieldName": "你的名字（招呼语署名）",
  "run.fieldNamePlaceholder": "必填，会出现在招呼语末尾",
  "run.hintRequired": "必填",
  "run.fieldLabel": "求职 tag",
  "run.fieldLabelPlaceholder": "留空走 BOSS 推荐 feed",
  "run.hintOptional": "选填",
  "run.fieldEndpoint": "AI 端点",
  "run.hintSetInConfig": "在「配置」tab 设",
  "run.llmReadFailed": "读取失败：{err}",
  "run.noKey": "缺 Key",
  "run.goConfigForKey": "去「配置」tab 选端点并填 API key",
  "run.noModelTag": "（未填 model）",
  "run.defaultEndpoint": "OpenAI 默认端点",
  "run.fieldDryRun": "Dry Run（只生成不发送）",
  "run.dryRunDesc": "只生成不发送（推荐先 dry run 一次）",
  "run.fieldResume": "简历 PDF",
  "run.resumeHint": "必填 · 拖入或选择",
  "run.uploading": "上传中…",
  "run.currentResume": "当前简历：{filename}",
  "run.replaceHint": "拖入新 PDF 可替换，或",
  "run.dropPrompt": "把简历 PDF 拖进来，或点这里打开文件浏览器 —— 上传一次，之后不用再传",
  "run.noResumeWarn": "没设置简历时点「开始」会直接报错。",
  "run.onlyPdf": "只接受 PDF 文件",
  "run.checkBadge": "检查",
  "run.errNeedName": "请填用户名（会出现在招呼语末尾的署名）",
  "run.errNeedAi": "还没配 AI —— 去「配置」tab 选端点并填 API key",
  "run.errNeedModel": "还没填模型（model）—— 去「配置」tab 选个预设会自动填，或手填 LLM_MODEL",
  "run.errNeedResume": "请先上传简历 PDF（拖进来或点「选择文件」）",
  "run.logStartFailed": "[start_run 失败] {err}",
  "run.logStopFailed": "[stop_run 失败] {err}",
  "run.logChromeClosed": "[已关 Chrome，下次启动会重新打开]",
  "run.logShutdownFailed": "[shutdown_browser 失败] {err}",
  "run.errorTitle": "▌ 出问题了？",
  "run.errorDesc": "复制日志贴给作者，或贴到 issues —— 不会自动发送任何东西。",
  "run.copyOk": "✓ 已复制日志，粘贴给作者或贴到 issues 即可",
  "run.copyFail": "复制失败 —— 日志就在下面面板，可手动全选复制",
  "run.logDir": "日志文件夹：{dir}",
  "run.panelProgress": "进度事件",
  "run.panelLog": "日志",
  "run.noEvents": "还没事件 ——",
  "run.noLogs": "还没日志",

  // ---- Config 页 ----
  "config.title": "配置",
  "config.editPrefix": "编辑",
  "config.editSuffix": "—— 仅本地，不会上传",
  "config.saved": "✓ 已保存",
  "config.unsaved": "未保存",
  // 语言选择器标签刻意双语，切错语言也能找回
  "config.language": "界面语言 · Language",
  "config.endpoint": "AI 端点",
  "config.endpointHint": "任意 OpenAI 兼容端点都行 —— 选个常用快捷自动填，或「自定义」手填",
  "config.preset": "常用快捷",
  "config.custom": "自定义",
  "config.baseUrlPlaceholder": "留空 = OpenAI 默认端点；如 https://api.deepseek.com",
  "config.modelPlaceholder": "如 deepseek-chat / gpt-4o / glm-4-plus",
  "config.secret": "密文",
  "config.signup": "申请：{url}",
  "config.keyConfiguredPlaceholder": "已配置 · 留空保持不变，输入则覆盖",
  "config.keyEmptyPlaceholder": "粘贴 API Key",
  "config.showKeyAria": "显示 key",
  "config.hideKeyAria": "隐藏 key",
  "config.presetKeyHint": "选了 {label}，记得在上面粘贴它的 API key 再保存。",
  "config.secretSetPlaceholder": "已设 · 留空保存即视为删除",
  "config.liveNote": "保存后即时生效——切回「运行」tab 就能用上新端点，无需重启 App。",

  // ---- Config 通用字段标签（原由后端回传，现前端按 key 翻译） ----
  "field.BOSS_USR_NAME": "你的名字（招呼语署名）",
  "field.BOSS_LABEL": "求职 tag（空走 BOSS 推荐 feed）",
  "field.BOSS_CHROME_PROFILE": "Chrome profile 目录（默认 ./chrome_profile）",
  "field.BOSS_MIN_MATCH_SCORE": "LLM 匹配分阈值（默认 50）",
  "field.BOSS_EXCLUDE_KEYWORDS": "岗位黑名单（用逗号分隔，如：外包,驻场）",
  "field.LOGLEVEL": "日志级别（默认 INFO）",

  // ---- History 页 ----
  "history.title": "历史",
  "history.subtitle": "最近的招呼语 · 调用成本汇总",
  "history.lettersHeading": "招呼语日志",
  "history.thTime": "时间",
  "history.thValidation": "校验",
  "history.thSent": "发送",
  "history.thLetter": "招呼语",
  "history.empty": "logs/letters.jsonl 是空的 —— 还没生成过招呼语",
  "history.costHeading": "LLM 成本 · 最近 1000 次",
  "history.statTotalCalls": "总调用次数",
  "history.statTotalCost": "总成本 (¥)",
  "history.statProviderCalls": "{provider} · {calls} 次",
  "history.jdPreview": "岗位预览",
};

const en: Dict = {
  // ---- App / top nav ----
  "tab.run": "Run",
  "tab.config": "Config",
  "tab.history": "History",
  "header.warn1": "Another Chrome window is automating",
  "header.warn2": "Don't close it manually",
  "header.askAi": "🆘 Ask AI for help",

  // ---- "Copy info for AI" ----
  "askai.btn": "Copy info for AI",
  "askai.ok": "✓ Copied — paste into any AI (ChatGPT / Claude …) and it can help you",
  "askai.fail": "Copy failed — try again, or use Copy logs",

  // ---- UpdateBanner ----
  "update.available": "New version v{latest} available · current v{current}",
  "update.download": "Download ↗",
  "update.dismiss": "Dismiss",

  // ---- common buttons / badges ----
  "btn.save": "Save →",
  "btn.saving": "Saving...",
  "btn.refresh": "Refresh ↻",
  "btn.pickFile": "Pick file…",
  "btn.start": "Start",
  "btn.stop": "▌ Stop",
  "btn.resetChrome": "Reset Chrome",
  "btn.copyLogs": "Copy logs",
  "btn.openIssues": "Open issues ↗",
  "btn.copyPath": "Copy path",
  "btn.show": "Show",
  "btn.hide": "Hide",
  "common.loading": "Loading...",

  // ---- Run page ----
  "run.title": "Run",
  "run.subtitle": "Fill in → Start → Watch it greet",
  "run.status": "Status",
  "run.statusRunningJob": "Running · job #{index}",
  "run.statusStarting": "Running · starting",
  "run.statusIdle": "Idle",
  "run.fieldName": "Your name (greeting signature)",
  "run.fieldNamePlaceholder": "Required, appended to the end of the greeting",
  "run.hintRequired": "Required",
  "run.fieldLabel": "Job tag",
  "run.fieldLabelPlaceholder": "Leave empty to use BOSS recommended feed",
  "run.hintOptional": "Optional",
  "run.fieldEndpoint": "AI Endpoint",
  "run.hintSetInConfig": "Set in Config tab",
  "run.llmReadFailed": "Read failed: {err}",
  "run.noKey": "No Key",
  "run.goConfigForKey": "Go to Config tab, pick an endpoint and enter the API key",
  "run.noModelTag": "(no model)",
  "run.defaultEndpoint": "OpenAI default endpoint",
  "run.fieldDryRun": "Dry Run (generate only)",
  "run.dryRunDesc": "Generate only, don't send (recommended for the first run)",
  "run.fieldResume": "Resume PDF",
  "run.resumeHint": "Required · drag or pick",
  "run.uploading": "Uploading…",
  "run.currentResume": "Current resume: {filename}",
  "run.replaceHint": "Drag a new PDF to replace, or",
  "run.dropPrompt": "Drag your resume PDF here, or click to open the file browser — upload once, no need to re-upload",
  "run.noResumeWarn": "Clicking Start without a resume will error out.",
  "run.onlyPdf": "Only PDF files are accepted",
  "run.checkBadge": "Check",
  "run.errNeedName": "Enter your name (used as the signature at the end of the greeting)",
  "run.errNeedAi": "AI not configured — go to Config tab, pick an endpoint and enter the API key",
  "run.errNeedModel": "No model set — pick a preset in Config tab to auto-fill, or set LLM_MODEL manually",
  "run.errNeedResume": "Upload a resume PDF first (drag it in or click Pick file)",
  "run.logStartFailed": "[start_run failed] {err}",
  "run.logStopFailed": "[stop_run failed] {err}",
  "run.logChromeClosed": "[Chrome closed, will reopen on next start]",
  "run.logShutdownFailed": "[shutdown_browser failed] {err}",
  "run.errorTitle": "▌ Something wrong?",
  "run.errorDesc": "Copy the logs and send them to the author, or post to issues — nothing is sent automatically.",
  "run.copyOk": "✓ Logs copied — paste to the author or into issues",
  "run.copyFail": "Copy failed — logs are in the panel below, select and copy manually",
  "run.logDir": "Log folder: {dir}",
  "run.panelProgress": "Progress",
  "run.panelLog": "Log",
  "run.noEvents": "No events yet —",
  "run.noLogs": "No logs yet",

  // ---- Config page ----
  "config.title": "Config",
  "config.editPrefix": "Edit",
  "config.editSuffix": "— local only, never uploaded",
  "config.saved": "✓ Saved",
  "config.unsaved": "unsaved",
  "config.language": "界面语言 · Language",
  "config.endpoint": "AI Endpoint",
  "config.endpointHint": "Any OpenAI-compatible endpoint works — pick a preset to auto-fill, or choose Custom to enter manually",
  "config.preset": "Preset",
  "config.custom": "Custom",
  "config.baseUrlPlaceholder": "Empty = OpenAI default endpoint; e.g. https://api.deepseek.com",
  "config.modelPlaceholder": "e.g. deepseek-chat / gpt-4o / glm-4-plus",
  "config.secret": "secret",
  "config.signup": "Sign up: {url}",
  "config.keyConfiguredPlaceholder": "Configured · leave empty to keep, type to overwrite",
  "config.keyEmptyPlaceholder": "Paste API Key",
  "config.showKeyAria": "Show key",
  "config.hideKeyAria": "Hide key",
  "config.presetKeyHint": "Selected {label} — remember to paste its API key above before saving.",
  "config.secretSetPlaceholder": "Set · save empty to delete",
  "config.liveNote": "Takes effect immediately — switch back to the Run tab to use the new endpoint, no restart needed.",

  // ---- Config generic field labels ----
  "field.BOSS_USR_NAME": "Your name (greeting signature)",
  "field.BOSS_LABEL": "Job tag (empty uses BOSS recommended feed)",
  "field.BOSS_CHROME_PROFILE": "Chrome profile directory (default ./chrome_profile)",
  "field.BOSS_MIN_MATCH_SCORE": "LLM match score threshold (default 50)",
  "field.BOSS_EXCLUDE_KEYWORDS": "Job blacklist (comma-separated, e.g. 外包,驻场)",
  "field.LOGLEVEL": "Log level (default INFO)",

  // ---- History page ----
  "history.title": "History",
  "history.subtitle": "Recent greetings · cost summary",
  "history.lettersHeading": "Letters",
  "history.thTime": "Time",
  "history.thValidation": "Validation",
  "history.thSent": "Sent",
  "history.thLetter": "Letter",
  "history.empty": "logs/letters.jsonl is empty — no greetings generated yet",
  "history.costHeading": "LLM Cost · last 1000 calls",
  "history.statTotalCalls": "Total calls",
  "history.statTotalCost": "Total cost (¥)",
  "history.statProviderCalls": "{provider} · {calls} calls",
  "history.jdPreview": "JD Preview",
};

const messages: Record<Lang, Dict> = { zh, en };

/** 取一条文案；`{name}` 占位符用 vars 替换。缺失回退 zh → key 本身。 */
export function translate(
  lang: Lang,
  key: string,
  vars?: Record<string, string | number>,
): string {
  let s = messages[lang][key] ?? messages.zh[key] ?? key;
  if (vars) {
    for (const k of Object.keys(vars)) {
      s = s.split(`{${k}}`).join(String(vars[k]));
    }
  }
  return s;
}

/** 首次启动默认语言：跟随系统/浏览器 locale，zh* → 中文，其余 → 英文。
 * 之后用户在 Config 选过会落到 .env 的 BOSS_LANG，启动时读回覆盖这个默认。 */
export function detectLang(): Lang {
  try {
    const nav = navigator.language || "";
    return nav.toLowerCase().startsWith("zh") ? "zh" : "en";
  } catch {
    return "zh";
  }
}

export function isLang(v: unknown): v is Lang {
  return v === "zh" || v === "en";
}
