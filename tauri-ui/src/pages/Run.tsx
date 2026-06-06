import { useEffect, useRef, useState } from "react";
import { Channel } from "@tauri-apps/api/core";
import { ipc, type ProgressEvent, type RunConfig } from "../lib/ipc";
import { useRunStore } from "../store";

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

  // 自动滚动
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

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <div className="bg-white p-4 rounded-lg shadow-sm border border-slate-200">
        <div className="grid grid-cols-2 gap-4">
          <Field label="你的名字（招呼语署名）">
            <input
              type="text"
              value={usrName}
              onChange={(e) => setUsrName(e.target.value)}
              disabled={running}
              className="input"
              placeholder="必填"
            />
          </Field>
          <Field label="求职 tag">
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              disabled={running}
              className="input"
              placeholder="留空走 BOSS 推荐 feed"
            />
          </Field>
          <Field label="Provider">
            {providersError ? (
              <span className="text-red-600 text-sm">检测失败: {providersError}</span>
            ) : providers.length === 0 ? (
              <span className="text-amber-600 text-sm">
                没检测到 API key —— 去配置 tab 填一个
              </span>
            ) : (
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                disabled={running}
                className="input"
              >
                {providers.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            )}
          </Field>
          <Field label="">
            <label className="inline-flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                disabled={running}
              />
              DRY-RUN（只生成不发送）
            </label>
          </Field>
        </div>

        <div className="flex items-center gap-3 mt-4">
          <button
            onClick={handleStart}
            disabled={running || busy}
            className="btn-primary"
          >
            开始
          </button>
          <button
            onClick={handleStop}
            disabled={!running || busy}
            className="btn-danger"
          >
            停止
          </button>
          <button
            onClick={handleReset}
            disabled={running || busy}
            className="btn-secondary"
          >
            重置 Chrome
          </button>
          <span className="ml-auto text-sm text-slate-600">
            {running
              ? currentIndex !== null
                ? `运行中 · 当前 job #${currentIndex}`
                : "运行中..."
              : "idle"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="进度事件">
          <div
            ref={eventsScrollRef}
            className="bg-slate-50 rounded p-3 text-xs font-mono h-72 overflow-y-auto"
          >
            {events.length === 0 ? (
              <div className="text-slate-400">还没事件</div>
            ) : (
              events.map((ev, i) => <EventRow key={i} ev={ev} />)
            )}
          </div>
        </Panel>

        <Panel title="日志">
          <pre
            ref={logScrollRef}
            className="bg-slate-900 text-slate-100 rounded p-3 text-xs font-mono h-72 overflow-y-auto whitespace-pre-wrap"
          >
            {logs.length === 0 ? <span className="text-slate-500">还没日志</span> : logs.join("\n")}
          </pre>
        </Panel>
      </div>

      <style>{`
        .input {
          padding: 0.4rem 0.6rem; font-size: 14px;
          border: 1px solid #cbd5e1; border-radius: 0.375rem;
          background: white; outline: none; transition: border-color 0.15s;
          width: 100%;
        }
        .input:focus { border-color: #64748b; }
        .input:disabled { background: #f1f5f9; color: #64748b; }
        .btn-primary {
          padding: 0.5rem 1.25rem; font-size: 14px; font-weight: 500;
          background: #16a34a; color: white; border-radius: 0.375rem;
          transition: background 0.15s;
        }
        .btn-primary:hover:not(:disabled) { background: #15803d; }
        .btn-danger {
          padding: 0.5rem 1.25rem; font-size: 14px; font-weight: 500;
          background: #dc2626; color: white; border-radius: 0.375rem;
        }
        .btn-danger:hover:not(:disabled) { background: #b91c1c; }
        .btn-secondary {
          padding: 0.5rem 1.25rem; font-size: 14px; font-weight: 500;
          background: white; color: #475569; border: 1px solid #cbd5e1;
          border-radius: 0.375rem;
        }
        .btn-secondary:hover:not(:disabled) { background: #f1f5f9; }
        .btn-primary:disabled, .btn-danger:disabled, .btn-secondary:disabled {
          opacity: 0.5; cursor: not-allowed;
        }
      `}</style>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      {label && <label className="block text-sm text-slate-600 mb-1">{label}</label>}
      {children}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white p-4 rounded-lg shadow-sm border border-slate-200">
      <h3 className="font-medium text-sm text-slate-700 mb-2">{title}</h3>
      {children}
    </div>
  );
}

const KIND_STYLES: Record<string, string> = {
  browser_started: "text-slate-500",
  login_ok: "text-emerald-700",
  job_found: "text-blue-700",
  job_skipped: "text-slate-500",
  letter_sent: "text-emerald-700 font-medium",
  feed_exhausted: "text-purple-700 font-medium",
  loop_ended: "text-purple-700 font-medium",
  error: "text-red-700 font-medium",
};

function EventRow({ ev }: { ev: ProgressEvent }) {
  const payload = Object.entries(ev.payload)
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(" ");
  return (
    <div className={`py-0.5 ${KIND_STYLES[ev.kind] ?? "text-slate-700"}`}>
      <span className="opacity-70">[{ev.kind}]</span> {payload}
    </div>
  );
}
