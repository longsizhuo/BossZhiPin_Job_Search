import { useEffect, useState } from "react";
import { ipc, type EnvField } from "../lib/ipc";

// 配置页：.env 编辑
// monochrome 设计：editorial 表单 —— 每个字段 key 用反色 mono 标签
// 错误信息用黑边粗框 + 黑底白字标签替代红色
export default function ConfigPage() {
  const [fields, setFields] = useState<EnvField[]>([]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const { fields } = await ipc.getEnvFields();
      setFields(fields);
      setEdits({});
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  function setField(key: string, value: string) {
    setSaved(false);
    setEdits((prev) => ({ ...prev, [key]: value }));
  }

  function valueFor(key: string, fallback: string): string {
    return key in edits ? edits[key] : fallback;
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await ipc.writeEnvFields(edits);
      setSaved(true);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  const dirty = Object.keys(edits).length > 0;

  return (
    <div className="space-y-10">
      {/* === 标题段 === */}
      <section className="flex items-end justify-between gap-6 pb-4 border-b-2 border-[var(--ink)]">
        <div>
          <h2 className="font-serif text-5xl leading-none tracking-tight">
            配置 <span className="italic font-normal">/ Config</span>
          </h2>
          <p className="mono-tag mt-3">
            编辑 <span className="text-[var(--ink)]">.env</span> —— 仅本地，不会上传
          </p>
        </div>
        <div className="flex items-center gap-4">
          {saved && !dirty && (
            <span className="badge-invert">✓ Saved</span>
          )}
          {dirty && (
            <span className="badge-outline italic">unsaved · 未保存</span>
          )}
          <button
            onClick={save}
            disabled={!dirty || saving}
            className="btn"
          >
            {saving ? "保存中..." : "保存 →"}
          </button>
        </div>
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

      {/* === 表单 === */}
      <section>
        {loading ? (
          <div className="font-mono text-sm text-[var(--muted-fg)] italic">
            Loading...
          </div>
        ) : (
          <div className="divide-y divide-[var(--border-light)]">
            {fields.map((f) => (
              <div key={f.key} className="py-6 grid grid-cols-1 md:grid-cols-[200px_1fr] gap-4 md:gap-10 items-start">
                {/* 左：key + 描述 */}
                <div>
                  <div className="font-mono text-xs uppercase tracking-widest bg-[var(--ink)] text-[var(--paper)] inline-block px-2 py-1">
                    {f.key}
                  </div>
                  <p className="mt-2 text-sm font-serif leading-snug text-[var(--ink)]">
                    {f.label}
                  </p>
                  {f.isSecret && (
                    <p className="mt-1 text-[10px] font-mono uppercase tracking-widest text-[var(--muted-fg)] italic">
                      secret · 密文
                    </p>
                  )}
                </div>
                {/* 右：输入 */}
                <div>
                  <input
                    type={f.isSecret ? "password" : "text"}
                    value={valueFor(f.key, f.value)}
                    onChange={(e) => setField(f.key, e.target.value)}
                    className="field-input font-mono"
                    placeholder={
                      f.isSecret ? "已设 · 留空保存即视为删除" : ""
                    }
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* === 说明 === */}
      <section className="border-t-4 border-[var(--ink)] pt-6">
        <p className="text-sm font-serif italic text-[var(--muted-fg)] leading-relaxed max-w-2xl">
          保存后 .env 立即更新；但 LLM client 在程序启动时已经读过 API key，
          要让新值生效请退出 App 重新打开。
        </p>
      </section>
    </div>
  );
}
