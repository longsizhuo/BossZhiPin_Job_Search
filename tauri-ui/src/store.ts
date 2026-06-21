/** 全局状态：当前是否在 run、最近事件、最近日志。Zustand。
 * 之所以全局：跨 tab 切换不丢运行状态 + 不丢已收的事件。 */
import { create } from "zustand";
import type { ProgressEvent } from "./lib/ipc";

const MAX_EVENTS = 500;
const MAX_LOGS = 1000;

type RunState = {
  running: boolean;
  events: ProgressEvent[];
  logs: string[];
  currentIndex: number | null;  // 当前 job_index（从 job_found 提取）

  // Form states preserved across tabs
  formUsrName: string;
  formLabel: string;
  formDryRun: boolean;

  setRunning: (running: boolean) => void;
  pushEvent: (ev: ProgressEvent) => void;
  pushLog: (line: string) => void;
  clear: () => void;

  setFormState: (state: Partial<Pick<RunState, "formUsrName" | "formLabel" | "formDryRun">>) => void;
};

export const useRunStore = create<RunState>((set) => ({
  running: false,
  events: [],
  logs: [],
  currentIndex: null,

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
  setFormState: (state) => set((s) => ({ ...s, ...state })),
}));
