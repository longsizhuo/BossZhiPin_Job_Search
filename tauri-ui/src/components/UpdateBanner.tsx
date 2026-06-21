import { useEffect, useState } from "react";
import { ipc, type UpdateInfo } from "../lib/ipc";

// 「有新版」横幅：挂载时静默查一次 GitHub 最新 release。
// 只提示不自动安装——点「前往下载」用系统浏览器打开 release 页，下载/安装手动。
// 没新版 / 没网 / 用户关掉本次提示时不渲染任何东西。
export default function UpdateBanner() {
  const [info, setInfo] = useState<UpdateInfo | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let alive = true;
    // 后端 check_for_update 永不抛错；catch 只是兜 IPC 层意外，绝不打扰用户。
    ipc.checkForUpdate()
      .then((r) => {
        if (alive && r.hasUpdate) setInfo(r);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  if (!info || dismissed) return null;

  return (
    <div className="bg-[var(--ink)] text-[var(--paper)] text-[11px] font-mono uppercase tracking-widest">
      <div className="max-w-7xl mx-auto px-8 py-2 flex items-center gap-4">
        <span>
          新版本 v{info.latest} 可用 · 当前 v{info.current}
        </span>
        <button
          onClick={() => ipc.openReleasePage(info.url).catch(() => {})}
          className="underline underline-offset-2 hover:opacity-70 transition-opacity"
        >
          前往下载 ↗
        </button>
        <button
          onClick={() => setDismissed(true)}
          className="ml-auto hover:opacity-70 transition-opacity"
          aria-label="关闭提示"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
