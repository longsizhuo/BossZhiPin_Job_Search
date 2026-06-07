import { useState } from "react";
import RunPage from "./pages/Run";
import ConfigPage from "./pages/Config";
import HistoryPage from "./pages/History";
import { useRunStore } from "./store";

type Tab = "run" | "config" | "history";

// 顶部标题 + tab 区域
// 设计：editorial 风格 —— 大号衬线标题 + 字距夸张的小 caps tab
// 当前 tab 用底部黑色粗线表示，而不是 pill 反色块
export default function App() {
  const [tab, setTab] = useState<Tab>("run");
  const running = useRunStore((s) => s.running);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b-4 border-[var(--ink)] bg-[var(--paper)]">
        <div className="max-w-7xl mx-auto px-8 pt-8 pb-2 flex items-baseline gap-10">
          {/* 主标题：oversized serif italic，作为视觉锚点 */}
          <h1 className="font-serif italic text-3xl md:text-4xl leading-none tracking-tight">
            Boss<span className="not-italic font-normal">·</span>Zhipin
            <span className="block text-[10px] not-italic font-mono uppercase tracking-widest text-[var(--muted-fg)] mt-1">
              Auto Greeting · Job Helper
            </span>
          </h1>

          {/* tab 群：uppercase mono，当前项底部 4px 黑线 */}
          <nav className="flex gap-8 self-end pb-1">
            <TabButton current={tab} value="run" onClick={setTab}>
              <span className="inline-flex items-center gap-2">
                运行 · Run
                {running && (
                  // 运行中标记：闪烁的黑色实心方块（不是绿色圆点）
                  <span className="inline-block w-1.5 h-1.5 bg-[var(--ink)] animate-pulse" />
                )}
              </span>
            </TabButton>
            <TabButton current={tab} value="config" onClick={setTab}>
              配置 · Config
            </TabButton>
            <TabButton current={tab} value="history" onClick={setTab}>
              历史 · History
            </TabButton>
          </nav>

          {/* 右侧提示语 */}
          <span className="ml-auto self-end pb-1 max-w-[240px] text-[10px] font-mono uppercase tracking-widest text-[var(--muted-fg)] leading-relaxed">
            另一个 Chrome 窗口正在自动化
            <br />
            请勿手动关闭
          </span>
        </div>
      </header>

      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto px-8 py-10">
          {tab === "run" && <RunPage />}
          {tab === "config" && <ConfigPage />}
          {tab === "history" && <HistoryPage />}
        </div>
      </main>
    </div>
  );
}

function TabButton({
  current,
  value,
  onClick,
  children,
}: {
  current: Tab;
  value: Tab;
  onClick: (t: Tab) => void;
  children: React.ReactNode;
}) {
  const active = current === value;
  return (
    <button
      onClick={() => onClick(value)}
      className={[
        "pb-2 text-[11px] font-mono uppercase tracking-widest transition-colors duration-100",
        // active：底部 4px 黑线 + 加粗黑字；inactive：弱灰 + hover 时浮现细底线
        active
          ? "text-[var(--ink)] border-b-[3px] border-[var(--ink)] font-semibold"
          : "text-[var(--muted-fg)] border-b-[3px] border-transparent hover:text-[var(--ink)] hover:border-[var(--border-light)]",
      ].join(" ")}
    >
      {children}
    </button>
  );
}
