/** 类型化的 pyInvoke 封装，所有跟 Python 后端的 IPC 调用都从这里走。
 * 改 backend 命令 / 返回类型时同步改这里，TypeScript 报错就是 contract 断了的信号。 */
import { pyInvoke } from "tauri-plugin-pytauri-api";

// ---------- types ----------

export type EventKind =
  | "browser_started"
  | "login_ok"
  | "job_found"
  | "job_skipped"
  | "letter_sent"
  | "feed_exhausted"
  | "loop_ended"
  | "error";

export type ProgressEvent = {
  kind: EventKind;
  payload: Record<string, unknown>;
};

export type RunConfig = {
  usrName: string;
  label: string;
  dryRun: boolean;
  resumePath?: string;
};

// LLM 端点预设（自动填 base_url + model 的快捷项；不是支持范围的限制）。
export type LlmPreset = {
  name: string;
  label: string;
  baseUrl: string;
  model: string;
  signupUrl: string;
};

// 当前 LLM 端点配置 + 预设列表。hasKey 只说有没有配 key，不回传明文。
export type LlmConfig = {
  baseUrl: string;
  model: string;
  hasKey: boolean;
  presets: LlmPreset[];
};

export type EnvField = {
  key: string;
  label: string;
  isSecret: boolean;
  value: string;
};

// 当前简历：文件名 + 绝对路径。没设置 / 文件不在时后端返回 null。
export type ResumeInfo = {
  filename: string;
  path: string;
};

export type LetterRecord = {
  ts: string;
  provider: string;
  model: string;
  dry_run: boolean;
  validation_ok: boolean;
  validation_reasons: string[];
  sent: boolean;
  letter_len: number;
  job_description: string;
  letter: string;
};

export type TelemetrySummary = {
  total_calls: number;
  total_cost_cny: number;
  by_provider: Record<string, {
    calls: number;
    input_tokens: number;
    output_tokens: number;
    cost_cny: number;
  }>;
};

// ---------- wrappers ----------

export const ipc = {
  isRunning: () => pyInvoke<{ running: boolean }>("is_running", {}),
  // LLM 端点：选预设/自定义 + base_url + model + key。apiKey 留空 = 不动已存 key。
  getLlmConfig: () => pyInvoke<LlmConfig>("get_llm_config", {}),
  setLlmConfig: (baseUrl: string, model: string, apiKey: string) =>
    pyInvoke<{ status: string }>("set_llm_config", { baseUrl, model, apiKey }),
  startRun: (config: RunConfig, progressChannel: unknown, logChannel: unknown) =>
    pyInvoke<{ status: string }>("start_run", { config, progressChannel, logChannel }),
  stopRun: () => pyInvoke<{ status: string }>("stop_run", {}),
  shutdownBrowser: () => pyInvoke<{ status: string }>("shutdown_browser", {}),
  getEnvFields: () => pyInvoke<{ fields: EnvField[] }>("get_env_fields", {}),
  writeEnvFields: (updates: Record<string, string>) =>
    pyInvoke<{ status: string }>("write_env_fields", { updates }),
  // 简历：set_resume 把拖入的 PDF 复制进 app 数据目录的 resume/；get_resume 读回当前简历。
  setResume: (path: string) =>
    pyInvoke<{ filename: string; path: string }>("set_resume", { path }),
  getResume: () => pyInvoke<{ resume: ResumeInfo | null }>("get_resume", {}),
  getLetters: (limit: number = 200) =>
    pyInvoke<{ letters: LetterRecord[] }>("get_letters", { limit }),
  getTelemetrySummary: () =>
    pyInvoke<{ summary: TelemetrySummary }>("get_telemetry_summary", {}),
  // 检查更新：查 GitHub 最新 release。后端永不抛错，没网时 hasUpdate=false。
  checkForUpdate: () =>
    pyInvoke<UpdateInfo>("check_for_update", {}),
  // 用系统浏览器打开下载页（后端做了 URL 白名单校验）。
  openReleasePage: (url: string) =>
    pyInvoke<{ status: string }>("open_release_page", { url }),
};

// 检查更新返回：当前版本 / 最新版本 / 下载页 URL / 是否有新版。
export type UpdateInfo = {
  current: string;
  latest: string;
  url: string;
  hasUpdate: boolean;
};
