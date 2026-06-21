import { useEffect, useRef, useState } from "react";
import { Channel } from "@tauri-apps/api/core";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import { ipc, type ProgressEvent, type RunConfig, type ResumeInfo, type LlmConfig } from "../lib/ipc";
import { useRunStore } from "../store";

// 运行页：editorial 三段式布局
// 1) 顶部 H2 + 状态副标题
// 2) 表单（底部边框输入，无圆角）
// 3) 控制按钮行（黑底白字反色）
// 4) 双面板：进度事件 + 日志（日志保留黑底白字，刚好契合 monochrome）
export default function RunPage() {
  // AI 端点在「配置」tab 设；运行页只读展示 + 校验是否配好了 key。
  const [llmCfg, setLlmCfg] = useState<LlmConfig | null>(null);
  const [llmError, setLlmError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // 简历（拖拽上传）
  const [resume, setResumeInfo] = useState<ResumeInfo | null>(null);
  const [resumeBusy, setResumeBusy] = useState(false);
  const [resumeError, setResumeError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  // 开始前校验的内联报错（替代生硬的 alert）
  const [startError, setStartError] = useState<string | null>(null);
  // 出错卡片：复制日志反馈 + 日志路径（懒加载）
  const [copyMsg, setCopyMsg] = useState<string | null>(null);
  const [logPaths, setLogPaths] = useState<{ dir: string } | null>(null);

  // Global form states
  const usrName = useRunStore((s) => s.formUsrName);
  const label = useRunStore((s) => s.formLabel);
  const dryRun = useRunStore((s) => s.formDryRun);
  const setFormState = useRunStore((s) => s.setFormState);

  const running = useRunStore((s) => s.running);
  const events = useRunStore((s) => s.events);
  const logs = useRunStore((s) => s.logs);
  const currentIndex = useRunStore((s) => s.currentIndex);
  const setRunning = useRunStore((s) => s.setRunning);
  const pushEvent = useRunStore((s) => s.pushEvent);
  const pushLog = useRunStore((s) => s.pushLog);
  const clear = useRunStore((s) => s.clear);

  const logScrollRef = useRef<HTMLPreElement>(null);
  const eventsScrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    ipc.getLlmConfig()
      .then((cfg) => setLlmCfg(cfg))
      .catch((e) => setLlmError(String(e)));

    ipc.getEnvFields().then(({ fields }) => {
      const stateUpdate: Record<string, any> = {};
      const nameField = fields.find(f => f.key === "BOSS_USR_NAME");
      if (nameField && nameField.value && !useRunStore.getState().formUsrName) {
        stateUpdate.formUsrName = nameField.value;
      }
      
      const labelField = fields.find(f => f.key === "BOSS_LABEL");
      if (labelField && labelField.value && !useRunStore.getState().formLabel) {
        stateUpdate.formLabel = labelField.value;
      }
      
      if (Object.keys(stateUpdate).length > 0) {
        setFormState(stateUpdate);
      }
    }).catch(() => {});
  }, []);

  // 挂载时读回当前简历（standalone 下持久化在 app 数据目录的 resume/）
  useEffect(() => {
    ipc.getResume()
      .then(({ resume }) => setResumeInfo(resume))
      .catch(() => {});
  }, []);

  // 拖拽上传：监听 webview 级 drag-drop 事件。这是 core API（@tauri-apps/api/webview），
  // 已被 capabilities 的 core:default 覆盖，不需要额外 plugin / ACL 配置。
  // 用 useRunStore.getState() 读 running 最新值，避免把 running 放进 deps 反复重订阅。
  useEffect(() => {
    let unlisten: (() => void) | undefined;
    let cancelled = false;
    getCurrentWebview()
      .onDragDropEvent((event) => {
        const p = event.payload;
        const isRunning = useRunStore.getState().running;
        if (p.type === "enter" || p.type === "over") {
          if (!isRunning) setDragging(true);
        } else if (p.type === "leave") {
          setDragging(false);
        } else if (p.type === "drop") {
          setDragging(false);
          if (isRunning) return;
          const pdf = p.paths.find((x) => x.toLowerCase().endsWith(".pdf"));
          if (!pdf) {
            setResumeError("只接受 PDF 文件");
            return;
          }
          setResumeBusy(true);
          setResumeError(null);
          ipc.setResume(pdf)
            .then((info) => setResumeInfo(info))
            .catch((e) => setResumeError(String(e)))
            .finally(() => setResumeBusy(false));
        }
      })
      .then((fn) => {
        if (cancelled) fn();
        else unlisten = fn;
      });
    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, []);

  // 文件选择器上传：webview 的 <input type=file> 给不到真实路径，只能读字节再传。
  // 跟拖拽并存——已有简历时也能点「选择文件」换，不是只剩拖拽。
  const fileInputRef = useRef<HTMLInputElement>(null);

  function arrayBufferToBase64(buf: ArrayBuffer): string {
    const bytes = new Uint8Array(buf);
    let binary = "";
    const chunk = 0x8000; // 分块避免 String.fromCharCode 参数过多爆栈
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
    }
    return btoa(binary);
  }

  async function onFilePicked(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // 重置：允许再次选同一个文件也能触发 change
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setResumeError("只接受 PDF 文件");
      return;
    }
    setResumeBusy(true);
    setResumeError(null);
    try {
      const b64 = arrayBufferToBase64(await file.arrayBuffer());
      const info = await ipc.setResumeBytes(file.name, b64);
      setResumeInfo(info);
    } catch (err) {
      setResumeError(String(err));
    } finally {
      setResumeBusy(false);
    }
  }

  // 自动滚动到底
  useEffect(() => {
    if (logScrollRef.current) {
      logScrollRef.current.scrollTop = logScrollRef.current.scrollHeight;
    }
  }, [logs.length]);
  useEffect(() => {
    if (eventsScrollRef.current) {
      eventsScrollRef.current.scrollTop = eventsScrollRef.current.scrollHeight;
    }
  }, [events.length]);

  async function handleStart() {
    // 开始前的拦截统一走内联 startError（不再用生硬的原生 alert）。
    // 校验顺序跟后端 start_run 的 pre-flight 对齐，让用户秒级看到缺了啥，
    // 而不是 run 闪一下、错误埋进日志面板。
    setStartError(null);
    if (!usrName.trim()) {
      setStartError("请填用户名（会出现在招呼语末尾的署名）");
      return;
    }
    if (!llmCfg || !llmCfg.hasKey) {
      setStartError("还没配 AI —— 去「配置」tab 选端点并填 API key");
      return;
    }
    if (!llmCfg.model) {
      // 缺 model 时后端 _build_client 会在第一个岗位抛错 break 掉整个 run，提前拦
      setStartError("还没填模型（model）—— 去「配置」tab 选个预设会自动填，或手填 LLM_MODEL");
      return;
    }
    if (!resume) {
      // 后端 start_run 第一道就是 current_resume() is None → ValueError；前端先拦，
      // 避免 run 闪一下 on→off、错误只埋在日志里。
      setStartError("请先上传简历 PDF（拖进来或点「选择文件」）");
      return;
    }
    setBusy(true);
    clear();
    setRunning(true);

    const progressChannel = new Channel<ProgressEvent>((ev) => pushEvent(ev));
    const logChannel = new Channel<string>((line) => pushLog(line));

    const config: RunConfig = {
      usrName: usrName.trim(),
      label: label.trim(),
      dryRun,
    };

    try {
      await ipc.startRun(config, progressChannel, logChannel);
    } catch (e) {
      pushLog(`[start_run 失败] ${e}`);
      setRunning(false);
    } finally {
      setBusy(false);
    }
  }

  async function handleStop() {
    setBusy(true);
    try {
      await ipc.stopRun();
    } catch (e) {
      pushLog(`[stop_run 失败] ${e}`);
    } finally {
      setBusy(false);
    }
  }

  async function handleReset() {
    setBusy(true);
    try {
      await ipc.shutdownBrowser();
      pushLog("[已关 Chrome，下次启动会重新打开]");
    } catch (e) {
      pushLog(`[shutdown_browser 失败] ${e}`);
    } finally {
      setBusy(false);
    }
  }

  // 出错时的"把日志发我"入口：检测进度事件里有没有 error / loop_ended(error)。
  const hasError = events.some(
    (e) => e.kind === "error" || (e.kind === "loop_ended" && e.payload?.reason === "error")
  );

  // 出错后懒加载一次日志目录路径，告诉用户文件在哪、可手动附带。
  useEffect(() => {
    if (hasError && !logPaths) {
      ipc.getLogDir().then((p) => setLogPaths({ dir: p.dir })).catch(() => {});
    }
  }, [hasError, logPaths]);

  async function copyLogs() {
    // 复制当前日志面板缓冲到剪贴板——用户自己粘给作者 / 贴 issues，绝不自动发送。
    try {
      await navigator.clipboard.writeText(logs.join("\n"));
      setCopyMsg("✓ 已复制日志，粘贴给作者或贴到 issues 即可");
    } catch {
      setCopyMsg("复制失败 —— 日志就在下面面板，可手动全选复制");
    }
    setTimeout(() => setCopyMsg(null), 4000);
  }

  // 状态副标题：替代原本的右侧 idle/running 小字
  const statusLine = running
    ? currentIndex !== null
      ? `Running · 当前 job #${currentIndex}`
      : "Running · 启动中"
    : "Idle";

  return (
    <div className="space-y-10">
      {/* === 段落 1：标题 + 状态 === */}
      <section className="flex items-end justify-between gap-6 pb-4 border-b-2 border-[var(--ink)]">
        <div>
          <h2 className="font-serif text-5xl leading-none tracking-tight">
            运行 <span className="italic font-normal">/ Run</span>
          </h2>
          <p className="mono-tag mt-3">填表 → 开始 → 看着它打招呼</p>
        </div>
        <div className="text-right">
          <span className="mono-tag block">Status</span>
          <span
            className={[
              "font-mono text-sm uppercase tracking-widest mt-1 inline-block px-2 py-1",
              running
                ? "bg-[var(--ink)] text-[var(--paper)]"
                : "text-[var(--muted-fg)]",
            ].join(" ")}
          >
            {statusLine}
          </span>
        </div>
      </section>

      {/* === 段落 2：参数表单 === */}
      <section>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-8">
          <Field label="你的名字（招呼语署名）" hint="Required">
            <input
              type="text"
              value={usrName}
              onChange={(e) => setFormState({ formUsrName: e.target.value })}
              disabled={running}
              className="field-input"
              placeholder="必填，会出现在招呼语末尾"
            />
          </Field>

          <Field label="求职 tag" hint="Optional">
            <input
              type="text"
              value={label}
              onChange={(e) => setFormState({ formLabel: e.target.value })}
              disabled={running}
              className="field-input"
              placeholder="留空走 BOSS 推荐 feed"
            />
          </Field>

          <Field label="AI 端点" hint="在「配置」tab 设">
            {llmError ? (
              <div className="text-sm font-mono py-2 border-b-2 border-[var(--ink)]">
                <span className="badge-outline mr-2">ERROR</span>
                读取失败：{llmError}
              </div>
            ) : !llmCfg || !llmCfg.hasKey ? (
              <div className="text-sm font-mono py-2 border-b-2 border-[var(--ink)]">
                <span className="badge-invert mr-2">No Key</span>
                去「配置」tab 选端点并填 API key
              </div>
            ) : (
              // 只读展示：端点 + model 在配置页设，这里不再有下拉
              <div className="text-sm font-mono py-2 border-b-2 border-[var(--ink)] flex items-center gap-2 flex-wrap">
                <span className="badge-invert">{llmCfg.model || "（未填 model）"}</span>
                <span className="text-[var(--muted-fg)] text-xs break-all">
                  {llmCfg.baseUrl || "OpenAI 默认端点"}
                </span>
              </div>
            )}
          </Field>

          <Field label="Dry Run">
            <label className="inline-flex items-center gap-3 text-sm cursor-pointer py-2">
              {/* 自定义 checkbox：黑边方块，选中后填充黑色 */}
              <span
                className={[
                  "inline-flex items-center justify-center w-5 h-5 border-2 border-[var(--ink)] transition-colors duration-100",
                  dryRun
                    ? "bg-[var(--ink)] text-[var(--paper)]"
                    : "bg-[var(--paper)] text-transparent",
                ].join(" ")}
              >
                <input
                  type="checkbox"
                  checked={dryRun}
                  onChange={(e) => setFormState({ formDryRun: e.target.checked })}
                  disabled={running}
                  className="sr-only"
                />
                {/* 用 × 符号表示勾选，比 ✓ 更契合 editorial 风 */}
                <span className="text-xs font-bold leading-none">×</span>
              </span>
              <span className="font-mono uppercase tracking-widest text-xs">
                只生成不发送（推荐先 dry run 一次）
              </span>
            </label>
          </Field>
        </div>
      </section>

      {/* === 段落 2.5：简历拖拽上传 === */}
      <section>
        <div className="flex items-baseline justify-between">
          <label className="field-label">简历 PDF</label>
          <span className="text-[10px] font-mono uppercase tracking-widest text-[var(--muted-fg)] italic">
            Required · 拖入或选择
          </span>
        </div>
        {/* 隐藏的原生文件选择器：拖拽之外的另一条上传路径 */}
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          onChange={onFilePicked}
        />
        <div
          onClick={() => {
            if (!running) fileInputRef.current?.click();
          }}
          role="button"
          tabIndex={running ? -1 : 0}
          className={[
            "mt-2 border-2 border-dashed p-6 transition-colors duration-100",
            dragging
              ? "border-[var(--ink)] bg-[var(--ink)] text-[var(--paper)]"
              : "border-[var(--border-light)]",
            running ? "opacity-50" : "cursor-pointer hover:border-[var(--ink)]",
          ].join(" ")}
        >
          {resumeBusy ? (
            <p className="font-mono text-sm">上传中…</p>
          ) : resume ? (
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <span className="font-mono text-sm">
                <span className="mr-2">■</span>当前简历：{resume.filename}
              </span>
              <div className="flex items-center gap-3 flex-wrap">
                <span className="mono-tag">拖入新 PDF 可替换，或</span>
                <PickFileButton onPick={() => fileInputRef.current?.click()} disabled={running} />
              </div>
            </div>
          ) : (
            <>
              <p className="font-mono text-sm">
                <span className="mr-2">⤓</span>把简历 PDF 拖进来，或点这里打开文件浏览器 —— 上传一次，之后不用再传
              </p>
              <div className="mt-3 flex items-center gap-3 flex-wrap">
                <PickFileButton onPick={() => fileInputRef.current?.click()} disabled={running} />
              </div>
              <p className="mt-2 text-xs font-mono text-[var(--muted-fg)] italic">
                没设置简历时点「开始」会直接报错。
              </p>
            </>
          )}
          {resumeError && (
            <p className="mt-3 text-xs font-mono">
              <span className="badge-outline mr-2">ERROR</span>
              {resumeError}
            </p>
          )}
        </div>
      </section>

      {/* === 段落 3：动作按钮 === */}
      <section className="pt-6 border-t border-[var(--border-light)]">
        <div className="flex items-center gap-4 flex-wrap">
          <button
            onClick={handleStart}
            disabled={running || busy}
            className="btn"
          >
            开始 <span className="ml-1">→</span>
          </button>
          <button
            onClick={handleStop}
            disabled={!running || busy}
            className="btn-outline"
          >
            ▌ 停止
          </button>
          <button
            onClick={handleReset}
            disabled={running || busy}
            className="btn-ghost"
          >
            重置 Chrome
          </button>
        </div>
        {/* 开始前校验未过：内联报错（替代原生 alert），点哪个字段缺一目了然 */}
        {startError && (
          <div className="mt-4 border-2 border-[var(--ink)] p-3 flex items-start gap-3">
            <span className="badge-invert flex-shrink-0">检查</span>
            <span className="text-sm font-mono">{startError}</span>
          </div>
        )}
      </section>

      {/* === 段落 3.5：出错了？把日志发我（手动，不自动上报）=== */}
      {hasError && (
        <section className="border-2 border-[var(--ink)] p-5 space-y-3">
          <div className="flex items-center gap-3">
            <span className="badge-invert">▌ 出问题了？</span>
            <span className="text-sm font-serif italic text-[var(--muted-fg)]">
              复制日志贴给作者，或贴到 issues —— 不会自动发送任何东西。
            </span>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <button type="button" onClick={copyLogs} className="btn-outline text-xs">
              复制日志
            </button>
            <button
              type="button"
              onClick={() => ipc.openIssuesPage().catch(() => {})}
              className="btn-outline text-xs"
            >
              打开 issues ↗
            </button>
            {copyMsg && (
              <span className="text-xs font-mono text-[var(--muted-fg)]">{copyMsg}</span>
            )}
          </div>
          {logPaths && (
            <p className="text-xs font-mono text-[var(--muted-fg)] break-all">
              日志文件夹：{logPaths.dir}
              <button
                type="button"
                onClick={() =>
                  navigator.clipboard.writeText(logPaths.dir).catch(() => {})
                }
                className="ml-2 underline underline-offset-2 hover:opacity-70"
              >
                复制路径
              </button>
            </p>
          )}
        </section>
      )}

      {/* === 段落 4：双面板 === */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-0 border-2 border-[var(--ink)]">
        <Panel title="Progress · 进度事件" rightDivider>
          <div
            ref={eventsScrollRef}
            className="text-xs font-mono h-80 overflow-y-auto"
          >
            {events.length === 0 ? (
              <div className="text-[var(--muted-fg)] italic">
                还没事件 ——
              </div>
            ) : (
              events.map((ev, i) => <EventRow key={i} ev={ev} />)
            )}
          </div>
        </Panel>

        <Panel title="Log · 日志">
          {/* 日志区：黑底白字反色块，强化 monochrome 对比 */}
          <pre
            ref={logScrollRef}
            className="bg-[var(--ink)] text-[var(--paper)] p-4 text-xs font-mono h-80 overflow-y-auto whitespace-pre-wrap leading-relaxed"
          >
            {logs.length === 0 ? (
              <span className="opacity-50 italic">还没日志</span>
            ) : (
              logs.join("\n")
            )}
          </pre>
        </Panel>
      </section>
    </div>
  );
}

// 简历上传的「选择文件…」按钮——有/无简历两个分支共用，避免两处改一处漏。
// stopPropagation 是因为它常嵌在可点击的虚线框里，别冒泡再触发一次 picker。
function PickFileButton({ onPick, disabled }: { onPick: () => void; disabled: boolean }) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onPick();
      }}
      disabled={disabled}
      className="btn-outline text-xs"
    >
      选择文件…
    </button>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        {label && <label className="field-label">{label}</label>}
        {hint && (
          <span className="text-[10px] font-mono uppercase tracking-widest text-[var(--muted-fg)] italic">
            {hint}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

function Panel({
  title,
  children,
  rightDivider,
}: {
  title: string;
  children: React.ReactNode;
  rightDivider?: boolean;
}) {
  // panel 之间用一条黑色竖线分隔（仅 desktop）
  return (
    <div
      className={[
        "p-6",
        rightDivider ? "lg:border-r-2 lg:border-[var(--ink)]" : "",
        "border-b-2 lg:border-b-0 border-[var(--ink)] last:border-b-0",
      ].join(" ")}
    >
      <h3 className="mono-tag mb-4 text-[var(--ink)]">{title}</h3>
      {children}
    </div>
  );
}

// 事件类型 → 视觉表达
// monochrome 风：去掉所有颜色语义，改用字重 + 反色 + 前缀符号
// - 重要正向（letter_sent / feed_exhausted / loop_ended）：反色徽章
// - 错误（error）：粗黑边 + 前缀 ▌
// - 跳过类（job_skipped）：虚弱化文本
// - 其他：默认
type EventStyle = {
  variant: "default" | "invert" | "error" | "weak";
  prefix?: string;
};

const KIND_STYLES: Record<string, EventStyle> = {
  browser_started: { variant: "weak", prefix: "·" },
  login_ok: { variant: "default", prefix: "✓" },
  job_found: { variant: "default", prefix: "→" },
  job_skipped: { variant: "weak", prefix: "—" },
  scoring_degraded: { variant: "error", prefix: "⚠️" },
  letter_sent: { variant: "invert", prefix: "■" },
  feed_exhausted: { variant: "invert", prefix: "■" },
  loop_ended: { variant: "invert", prefix: "■" },
  error: { variant: "error", prefix: "▌" },
};

function EventRow({ ev }: { ev: ProgressEvent }) {
  const style = KIND_STYLES[ev.kind] ?? { variant: "default" };
  const payload = Object.entries(ev.payload)
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(" ");

  const classes = {
    default: "py-1 text-[var(--ink)]",
    invert:
      "py-1 px-2 -mx-2 my-0.5 bg-[var(--ink)] text-[var(--paper)] font-medium",
    error:
      "py-1 px-2 -mx-2 my-0.5 border-l-4 border-[var(--ink)] font-medium",
    weak: "py-1 text-[var(--muted-fg)]",
  }[style.variant];

  return (
    <div className={classes}>
      {style.prefix && <span className="mr-2">{style.prefix}</span>}
      <span className="uppercase tracking-widest text-[10px]">[{ev.kind}]</span>{" "}
      <span className="opacity-80">{payload}</span>
    </div>
  );
}
