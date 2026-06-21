import { useEffect, useState } from "react";
import RunPage from "./pages/Run";
import ConfigPage from "./pages/Config";
import HistoryPage from "./pages/History";
import UpdateBanner from "./components/UpdateBanner";
import { useRunStore, useT } from "./store";
import { ipc } from "./lib/ipc";
import { isLang } from "./lib/i18n";

type Tab = "run" | "config" | "history";

// 顶部标题 + tab 区域
// 设计：editorial 风格 —— 大号衬线标题 + 字距夸张的小 caps tab
// 当前 tab 用底部黑色粗线表示，而不是 pill 反色块
export default function App() {
  const [tab, setTab] = useState<Tab>("run");
  const [helpMsg, setHelpMsg] = useState<string | null>(null);
  const running = useRunStore((s) => s.running);
  const setLang = useRunStore((s) => s.setLang);
  const t = useT();

  // 「问 AI 帮忙」：把 app 上下文 + 当前实时日志缓冲打成一段求助文本复制到剪贴板，
  // 用户粘到任意聊天 AI 即可。常驻 header，每个 tab 都点得到（不只出错时）。
  async function askAi() {
    try {
      const logs = useRunStore.getState().logs;
      const { text } = await ipc.getAiHelpReport(logs);
      await navigator.clipboard.writeText(text);
      setHelpMsg(t("askai.ok"));
    } catch {
      setHelpMsg(t("askai.fail"));
    }
    setTimeout(() => setHelpMsg(null), 6000);
  }

  // 启动时读回 .env 里存的 UI 语言，覆盖系统探测的默认。
  // 没设过（首次启动）则把探测到的默认落进 .env，让后端报错（读 BOSS_LANG）跟
  // 前端展示的语言一致——否则非中文用户首次见到的后端串会是中文。读/写失败都
  // 静默：大不了下次启动再探测一次，不打断使用。
  useEffect(() => {
    ipc.getLanguage()
      .then(({ lang }) => {
        if (isLang(lang)) {
          setLang(lang);
        } else {
          const detected = useRunStore.getState().lang;
          ipc.setLanguage(detected).catch(() => {});
        }
      })
      .catch(() => {});
  }, [setLang]);

  return (
    <div className="min-h-screen flex flex-col">
      <UpdateBanner />
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
                {t("tab.run")}
                {running && (
                  // 运行中标记：闪烁的黑色实心方块（不是绿色圆点）
                  <span className="inline-block w-1.5 h-1.5 bg-[var(--ink)] animate-pulse" />
                )}
              </span>
            </TabButton>
            <TabButton current={tab} value="config" onClick={setTab}>
              {t("tab.config")}
            </TabButton>
            <TabButton current={tab} value="history" onClick={setTab}>
              {t("tab.history")}
            </TabButton>
          </nav>

          {/* 右侧：常驻「问 AI」入口 + Chrome 提示语（复制成功时提示语临时换成反馈） */}
          <div className="ml-auto self-end pb-1 flex flex-col items-end gap-1.5 max-w-[260px]">
            <button
              onClick={askAi}
              className="text-[11px] font-mono uppercase tracking-widest border-2 border-[var(--ink)] px-2 py-1 hover:bg-[var(--ink)] hover:text-[var(--paper)] transition-colors duration-100"
            >
              {t("header.askAi")}
            </button>
            {helpMsg ? (
              <span className="text-[10px] font-mono text-right text-[var(--ink)] leading-relaxed">
                {helpMsg}
              </span>
            ) : (
              <span className="text-[10px] font-mono uppercase tracking-widest text-right text-[var(--muted-fg)] leading-relaxed">
                {t("header.warn1")}
                <br />
                {t("header.warn2")}
              </span>
            )}
          </div>
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
