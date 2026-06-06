import { useState } from "react";
import RunPage from "./pages/Run";
import ConfigPage from "./pages/Config";
import HistoryPage from "./pages/History";
import { useRunStore } from "./store";

type Tab = "run" | "config" | "history";

export default function App() {
  const [tab, setTab] = useState<Tab>("run");
  const running = useRunStore((s) => s.running);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center gap-6">
        <h1 className="text-lg font-semibold">BOSS Zhipin Helper</h1>
        <nav className="flex gap-1">
          <TabButton current={tab} value="run" onClick={setTab}>
            运行 {running && <span className="ml-1 inline-block w-2 h-2 bg-green-500 rounded-full animate-pulse" />}
          </TabButton>
          <TabButton current={tab} value="config" onClick={setTab}>配置</TabButton>
          <TabButton current={tab} value="history" onClick={setTab}>历史</TabButton>
        </nav>
        <span className="ml-auto text-xs text-slate-500">
          自动化 Chrome 在另一个窗口，请勿手动关闭
        </span>
      </header>

      <main className="flex-1 p-6 overflow-auto">
        {tab === "run" && <RunPage />}
        {tab === "config" && <ConfigPage />}
        {tab === "history" && <HistoryPage />}
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
      className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
        active
          ? "bg-slate-900 text-white"
          : "text-slate-600 hover:bg-slate-100"
      }`}
    >
      {children}
    </button>
  );
}
