import { useEffect, useState } from "react";
import { ipc, type LetterRecord, type TelemetrySummary } from "../lib/ipc";

// 历史页：editorial 表格
// monochrome 设计：
// - 表头 uppercase mono，底部 4px 黑线
// - 行 hover 反色
// - 校验/发送状态用 mono 符号 + 反色徽章，不用红绿色
// - 成本汇总用大号 serif 数字 + uppercase 小标签
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
    <div className="space-y-10">
      {/* === 标题段 === */}
      <section className="flex items-end justify-between gap-6 pb-4 border-b-2 border-[var(--ink)]">
        <div>
          <h2 className="font-serif text-5xl leading-none tracking-tight">
            历史 <span className="italic font-normal">/ History</span>
          </h2>
          <p className="mono-tag mt-3">
            最近的招呼语 · 调用成本汇总
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="btn-outline"
        >
          {loading ? "..." : "刷新 ↻"}
        </button>
      </section>

      {/* === 错误带 === */}
      {error && (
        <div className="border-2 border-[var(--ink)] p-4 flex items-start gap-3">
          <span className="badge-invert flex-shrink-0">ERROR</span>
          <pre className="text-sm font-mono whitespace-pre-wrap flex-1">
            {error}
          </pre>
        </div>
      )}

      {/* === 成本汇总 === */}
      {summary && <CostSummary summary={summary} />}

      {/* === 招呼语表格 === */}
      <section>
        <h3 className="mono-tag mb-3 text-[var(--ink)]">
          Letters · 招呼语日志
        </h3>
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b-4 border-[var(--ink)]">
              <Th>时间 · Time</Th>
              <Th>Provider</Th>
              <Th>Model</Th>
              <Th align="center">校验</Th>
              <Th align="center">发送</Th>
              <Th>招呼语 · Letter</Th>
            </tr>
          </thead>
          <tbody>
            {letters.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-3 py-12 text-center font-serif italic text-[var(--muted-fg)]"
                >
                  {loading
                    ? "Loading..."
                    : "logs/letters.jsonl 是空的 —— 还没生成过招呼语"}
                </td>
              </tr>
            ) : (
              letters.map((l, i) => <LetterRow key={i} l={l} />)
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function Th({
  children,
  align = "left",
}: {
  children: React.ReactNode;
  align?: "left" | "center";
}) {
  return (
    <th
      className={[
        "px-3 py-3 font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]",
        align === "center" ? "text-center" : "text-left",
      ].join(" ")}
    >
      {children}
    </th>
  );
}

function CostSummary({ summary }: { summary: TelemetrySummary }) {
  const providers = Object.entries(summary.by_provider);
  return (
    <section className="border-2 border-[var(--ink)] p-6">
      <h3 className="mono-tag mb-5 text-[var(--ink)]">
        LLM Cost · 最近 1000 次
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-x-8 gap-y-6">
        <Stat
          label="总调用次数"
          value={summary.total_calls.toString()}
          emphasis
        />
        <Stat
          label="总成本 (¥)"
          value={summary.total_cost_cny.toFixed(4)}
          emphasis
        />
        {providers.map(([provider, s]) => (
          <Stat
            key={provider}
            label={`${provider} · ${s.calls} 次`}
            value={`¥ ${s.cost_cny.toFixed(4)}`}
            sub={`in: ${s.input_tokens}  out: ${s.output_tokens}`}
          />
        ))}
      </div>
    </section>
  );
}

function Stat({
  label,
  value,
  sub,
  emphasis,
}: {
  label: string;
  value: string;
  sub?: string;
  emphasis?: boolean;
}) {
  // emphasis 项加左侧 4px 黑线，强化层级
  return (
    <div className={emphasis ? "border-l-4 border-[var(--ink)] pl-3" : ""}>
      <div className="mono-tag">{label}</div>
      <div className="font-serif text-3xl leading-none tracking-tight mt-2">
        {value}
      </div>
      {sub && (
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--muted-fg)] mt-2">
          {sub}
        </div>
      )}
    </div>
  );
}

function LetterRow({ l }: { l: LetterRecord }) {
  const [expanded, setExpanded] = useState(false);
  const time = new Date(l.ts).toLocaleString();

  return (
    <>
      <tr
        className="border-b border-[var(--border-light)] cursor-pointer transition-colors duration-100 hover:bg-[var(--ink)] hover:text-[var(--paper)] group"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-3 py-3 font-mono text-[11px] whitespace-nowrap">
          {time}
        </td>
        <td className="px-3 py-3 font-mono text-[11px] uppercase tracking-widest">
          {l.provider}
        </td>
        <td className="px-3 py-3 font-mono text-[11px]">{l.model}</td>
        <td className="px-3 py-3 text-center">
          {l.validation_ok ? (
            <span className="font-mono text-xs">✓ OK</span>
          ) : (
            <span
              className="font-mono text-xs border-b-2 border-current"
              title={l.validation_reasons.join(", ")}
            >
              ✗ FAIL
            </span>
          )}
        </td>
        <td className="px-3 py-3 text-center">
          {l.sent ? (
            // 已发：反色徽章，但 hover 反色后会变白底黑字，要做兼容
            <span className="font-mono text-[10px] uppercase tracking-widest bg-[var(--ink)] text-[var(--paper)] px-2 py-0.5 group-hover:bg-[var(--paper)] group-hover:text-[var(--ink)]">
              SENT
            </span>
          ) : l.dry_run ? (
            <span className="font-mono text-[10px] uppercase tracking-widest border border-current px-2 py-0.5">
              DRY
            </span>
          ) : (
            <span className="font-mono text-[10px] text-[var(--muted-fg)] group-hover:text-[var(--paper)]">
              —
            </span>
          )}
        </td>
        <td className="px-3 py-3 text-sm font-serif leading-snug">
          {expanded
            ? l.letter
            : l.letter.slice(0, 60) + (l.letter.length > 60 ? "..." : "")}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b-2 border-[var(--ink)] bg-[var(--muted)]">
          <td colSpan={6} className="px-3 py-5">
            <div className="space-y-3">
              <div>
                <span className="mono-tag block mb-1">
                  JD Preview · 岗位预览
                </span>
                <p className="text-sm font-serif leading-relaxed text-[var(--ink)]">
                  {l.job_description.slice(0, 300)}
                  {l.job_description.length > 300 && "..."}
                </p>
              </div>
              {!l.validation_ok && (
                <div className="border-l-4 border-[var(--ink)] pl-3">
                  <span className="badge-invert">Validation Failed</span>
                  <p className="text-sm font-mono mt-1">
                    {l.validation_reasons.join(", ")}
                  </p>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
