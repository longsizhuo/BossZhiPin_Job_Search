import { useEffect, useState } from "react";
import { ipc, type EnvField } from "../lib/ipc";

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
    <div className="max-w-3xl mx-auto">
      <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">配置 (.env)</h2>
          <div className="flex items-center gap-3">
            {saved && !dirty && (
              <span className="text-sm text-emerald-600">✓ 已保存</span>
            )}
            <button
              onClick={save}
              disabled={!dirty || saving}
              className="px-4 py-1.5 bg-slate-900 text-white rounded text-sm disabled:opacity-50"
            >
              {saving ? "保存中..." : "保存"}
            </button>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 text-red-700 border border-red-200 rounded p-3 mb-4 text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-slate-500">加载中...</div>
        ) : (
          <div className="space-y-3">
            {fields.map((f) => (
              <div key={f.key}>
                <label className="block text-sm text-slate-600 mb-1">
                  <span className="font-mono text-xs bg-slate-100 px-1.5 py-0.5 rounded mr-2">
                    {f.key}
                  </span>
                  {f.label}
                </label>
                <input
                  type={f.isSecret ? "password" : "text"}
                  value={valueFor(f.key, f.value)}
                  onChange={(e) => setField(f.key, e.target.value)}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded text-sm font-mono"
                  placeholder={f.isSecret ? "（已设，留空覆盖为删除）" : ""}
                />
              </div>
            ))}
          </div>
        )}

        <p className="mt-4 text-xs text-slate-500">
          保存后 .env 立刻更新；但 LLM client 在程序启动时已经读过 API key，
          要让新值生效请退出 App 重新打开。
        </p>
      </div>
    </div>
  );
}
