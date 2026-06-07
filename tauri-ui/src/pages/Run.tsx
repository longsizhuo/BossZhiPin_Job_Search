import { useEffect, useRef, useState } from "react";
import { Channel } from "@tauri-apps/api/core";
import { ipc, type ProgressEvent, type RunConfig } from "../lib/ipc";
import { useRunStore } from "../store";

// 运行页：editorial 三段式布局
// 1) 顶部 H2 + 状态副标题
// 2) 表单（底部边框输入，无圆角）
// 3) 控制按钮行（黑底白字反色）
// 4) 双面板：进度事件 + 日志（日志保留黑底白字，刚好契合 monochrome）
export default function RunPage() {
  const [providers, setProviders] = useState<string[]>([]);
  const [providersError, setProvidersError] = useState<string | null>(null);
  const [usrName, setUsrName] = useState("");
  const [label, setLabel] = useState("");
  const [provider, setProvider] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const [busy, setBusy] = useState(false);

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
    ipc.detectProviders()
      .then(({ providers }) => {
        setProviders(providers);
        if (providers.length > 0) setProvider(providers[0]);
      })
      .catch((e) => setProvidersError(String(e)));
  }, []);

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
    if (!usrName.trim()) {
      alert("请填用户名");
      return;
    }
    if (!provider) {
      alert("没有可用的 provider，先去配置 tab 填 API key");
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
      provider,
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
              onChange={(e) => setUsrName(e.target.value)}
              disabled={running}
              className="field-input"
              placeholder="必填，会出现在招呼语末尾"
            />
          </Field>

          <Field label="求职 tag" hint="Optional">
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              disabled={running}
              className="field-input"
              placeholder="留空走 BOSS 推荐 feed"
            />
          </Field>

          <Field label="LLM Provider">
            {providersError ? (
              <div className="text-sm font-mono py-2 border-b-2 border-[var(--ink)]">
                <span className="badge-outline mr-2">ERROR</span>
                检测失败：{providersError}
              </div>
            ) : providers.length === 0 ? (
              <div className="text-sm font-mono py-2 border-b-2 border-[var(--ink)]">
                <span className="badge-invert mr-2">No Key</span>
                去「配置」tab 填一个 API key
              </div>
            ) : (
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                disabled={running}
                className="field-input"
              >
                {providers.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
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
                  onChange={(e) => setDryRun(e.target.checked)}
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

      {/* === 段落 3：动作按钮 === */}
      <section className="flex items-center gap-4 flex-wrap pt-6 border-t border-[var(--border-light)]">
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
      </section>

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
