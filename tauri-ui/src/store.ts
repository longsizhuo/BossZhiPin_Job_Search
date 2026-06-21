/** 全局状态：当前是否在 run、最近事件、最近日志。Zustand。
 * 之所以全局：跨 tab 切换不丢运行状态 + 不丢已收的事件。 */
import { create } from "zustand";
import { useCallback } from "react";
import type { ProgressEvent } from "./lib/ipc";
import { type Lang, detectLang, translate } from "./lib/i18n";

const MAX_EVENTS = 500;
const MAX_LOGS = 1000;

type RunState = {
  running: boolean;
  events: ProgressEvent[];
  logs: string[];
  currentIndex: number | null;  // 当前 job_index（从 job_found 提取）

  // UI 语言：启动时按系统 locale 探测，App 挂载后用 .env 的 BOSS_LANG 覆盖。
  lang: Lang;

  // Form states preserved across tabs
  formUsrName: string;
  formLabel: string;
  formDryRun: boolean;

  setRunning: (running: boolean) => void;
  pushEvent: (ev: ProgressEvent) => void;
  pushLog: (line: string) => void;
  clear: () => void;
  setLang: (lang: Lang) => void;

  setFormState: (state: Partial<Pick<RunState, "formUsrName" | "formLabel" | "formDryRun">>) => void;
};

export const useRunStore = create<RunState>((set) => ({
  running: false,
  events: [],
  logs: [],
  currentIndex: null,

  lang: detectLang(),

  formUsrName: "",
  formLabel: "",
  formDryRun: true,

  setRunning: (running) => set({ running }),
  pushEvent: (ev) =>
    set((s) => {
      const events = [...s.events, ev].slice(-MAX_EVENTS);
      let currentIndex = s.currentIndex;
      if (ev.kind === "job_found" && typeof ev.payload.index === "number") {
        currentIndex = ev.payload.index;
      }
      let running = s.running;
      if (ev.kind === "loop_ended") {
        running = false;
      }
      return { events, currentIndex, running };
    }),
  pushLog: (line) => set((s) => ({ logs: [...s.logs, line].slice(-MAX_LOGS) })),
  clear: () => set({ events: [], logs: [], currentIndex: null }),
  setLang: (lang) => set({ lang }),
  setFormState: (state) => set((s) => ({ ...s, ...state })),
}));

/** 组件里取翻译函数：`const t = useT()`，`t("run.title")`。
 * 订阅 store.lang，切语言时所有用到的组件自动重渲染。 */
export function useT() {
  const lang = useRunStore((s) => s.lang);
  return useCallback(
    (key: string, vars?: Record<string, string | number>) => translate(lang, key, vars),
    [lang],
  );
}
