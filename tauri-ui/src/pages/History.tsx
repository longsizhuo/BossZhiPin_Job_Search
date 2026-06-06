import { useEffect, useState } from "react";
import { ipc, type LetterRecord, type TelemetrySummary } from "../lib/ipc";

export default function HistoryPage() {
  const [letters, setLetters] = useState<LetterRecord[]>([]);
  const [summary, setSummary] = useState<TelemetrySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [{ letters }, { summary }] = await Promise.all([
        ipc.getLetters(200),
        ipc.getTelemetrySummary(),
      ]);
      setLetters(letters.reverse()); // 最新的在最上
      setSummary(summary);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">历史</h2>
        <button
          onClick={refresh}
          disabled={loading}
          className="px-3 py-1 text-sm border border-slate-300 rounded hover:bg-slate-100"
        >
          {loading ? "..." : "刷新"}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 border border-red-200 rounded p-3 text-sm">
          {error}
        </div>
      )}

      {summary && <CostSummary summary={summary} />}

      <div className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr className="text-left text-xs text-slate-600">
              <th className="px-3 py-2">时间</th>
              <th className="px-3 py-2">Provider</th>
              <th className="px-3 py-2">Model</th>
              <th className="px-3 py-2 text-center">校验</th>
              <th className="px-3 py-2 text-center">发送</th>
              <th className="px-3 py-2">招呼语</th>
            </tr>
          </thead>
          <tbody>
            {letters.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-center text-slate-400">
                  {loading ? "加载中..." : "logs/letters.jsonl 是空的——还没生成过招呼语"}
                </td>
              </tr>
            ) : (
              letters.map((l, i) => <LetterRow key={i} l={l} />)
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CostSummary({ summary }: { summary: TelemetrySummary }) {
  const providers = Object.entries(summary.by_provider);
  return (
    <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-4">
      <h3 className="font-medium text-sm text-slate-700 mb-3">LLM 调用成本（最近 1000 次）</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <Stat label="总调用次数" value={summary.total_calls.toString()} />
        <Stat label="总成本 (¥)" value={summary.total_cost_cny.toFixed(4)} />
        {providers.map(([provider, s]) => (
          <Stat
            key={provider}
            label={`${provider} (${s.calls} 次)`}
            value={`¥ ${s.cost_cny.toFixed(4)}`}
            sub={`in: ${s.input_tokens}  out: ${s.output_tokens}`}
          />
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-slate-50 rounded p-2">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="font-mono text-base mt-0.5">{value}</div>
      {sub && <div className="text-xs text-slate-400 mt-0.5">{sub}</div>}
    </div>
  );
}

function LetterRow({ l }: { l: LetterRecord }) {
  const [expanded, setExpanded] = useState(false);
  const time = new Date(l.ts).toLocaleString();
  return (
    <>
      <tr className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <td className="px-3 py-2 text-xs text-slate-600 whitespace-nowrap">{time}</td>
        <td className="px-3 py-2 text-xs">{l.provider}</td>
        <td className="px-3 py-2 text-xs">{l.model}</td>
        <td className="px-3 py-2 text-center">
          {l.validation_ok ? (
            <span className="text-emerald-600">✓</span>
          ) : (
            <span className="text-red-600" title={l.validation_reasons.join(", ")}>✗</span>
          )}
        </td>
        <td className="px-3 py-2 text-center text-xs">
          {l.sent ? "已发" : l.dry_run ? "DRY" : "—"}
        </td>
        <td className="px-3 py-2 text-xs">
          {expanded ? l.letter : l.letter.slice(0, 60) + (l.letter.length > 60 ? "..." : "")}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-slate-200 bg-slate-50">
          <td colSpan={6} className="px-3 py-3 text-xs">
            <div className="mb-2">
              <span className="font-medium text-slate-700">JD 预览：</span>
              <span className="text-slate-600 ml-1">
                {l.job_description.slice(0, 300)}{l.job_description.length > 300 && "..."}
              </span>
            </div>
            {!l.validation_ok && (
              <div className="text-red-700">
                <span className="font-medium">校验失败：</span>
                {l.validation_reasons.join(", ")}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
