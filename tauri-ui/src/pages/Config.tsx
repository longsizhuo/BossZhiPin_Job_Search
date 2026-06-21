import { useEffect, useState } from "react";
import { ipc, type EnvField, type ProviderConfig } from "../lib/ipc";

// 配置页：.env 编辑
// monochrome 设计：editorial 表单 —— 每个字段 key 用反色 mono 标签
// 错误信息用黑边粗框 + 黑底白字标签替代红色
//
// 顶部「AI 服务商」段：选一家 + 填一个 key（取代以前并排的三个 API key 框，
// 小白会以为三个都得填）。下面是其余通用字段（名字 / tag / 模型选项…）。
export default function ConfigPage() {
  const [fields, setFields] = useState<EnvField[]>([]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 服务商段状态
  const [providerCfg, setProviderCfg] = useState<ProviderConfig | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  // null = 用户没动 key 框（保存时不传 key，不覆盖已存的）；字符串 = 用户输入了新 key
  const [keyEdit, setKeyEdit] = useState<string | null>(null);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [{ fields }, pc] = await Promise.all([
        ipc.getEnvFields(),
        ipc.getProviderConfig(),
      ]);
      setFields(fields);
      setEdits({});
      setProviderCfg(pc);
      setSelectedProvider(pc.active);
      setKeyEdit(null);
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

  function pickProvider(name: string) {
    setSaved(false);
    setSelectedProvider(name);
  }

  function editKey(value: string) {
    setSaved(false);
    setKeyEdit(value);
  }

  const providerDirty =
    providerCfg !== null &&
    (selectedProvider !== providerCfg.active || keyEdit !== null);
  const dirty = Object.keys(edits).length > 0 || providerDirty;

  async function save() {
    setSaving(true);
    setError(null);
    try {
      // 先存服务商（apiKey 留空 = 只切，不动已存 key），再存通用字段
      if (providerDirty) {
        await ipc.setProviderConfig(selectedProvider, keyEdit ?? "");
      }
      if (Object.keys(edits).length > 0) {
        await ipc.writeEnvFields(edits);
      }
      setSaved(true);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  const selectedMeta = providerCfg?.providers.find((p) => p.name === selectedProvider);

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

      {loading ? (
        <div className="font-mono text-sm text-[var(--muted-fg)] italic">
          Loading...
        </div>
      ) : (
        <>
          {/* === AI 服务商：选一家 + 填一个 key === */}
          {providerCfg && (
            <section className="space-y-4">
              <div>
                <label className="field-label">AI 服务商 / Provider</label>
                <p className="mt-1 text-xs font-mono text-[var(--muted-fg)] italic">
                  三家任选其一即可跑——选谁就填谁的 key
                </p>
              </div>

              {/* 分段选择器：每家一个按钮，已配过 key 的右上角打 ✓ */}
              <div className="flex flex-wrap gap-3">
                {providerCfg.providers.map((p) => {
                  const active = p.name === selectedProvider;
                  return (
                    <button
                      key={p.name}
                      onClick={() => pickProvider(p.name)}
                      className={[
                        "px-4 py-2 border-2 font-mono text-sm transition-colors duration-100",
                        active
                          ? "bg-[var(--ink)] text-[var(--paper)] border-[var(--ink)]"
                          : "bg-[var(--paper)] text-[var(--ink)] border-[var(--border-light)] hover:border-[var(--ink)]",
                      ].join(" ")}
                    >
                      {p.label}
                      {p.hasKey && <span className="ml-2">✓</span>}
                    </button>
                  );
                })}
              </div>

              {/* 当前选中那家的单个 key 框 */}
              <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-4 md:gap-10 items-start pt-2">
                <div>
                  <div className="font-mono text-xs uppercase tracking-widest bg-[var(--ink)] text-[var(--paper)] inline-block px-2 py-1">
                    {selectedMeta ? `${selectedMeta.label} API Key` : "API Key"}
                  </div>
                  <p className="mt-2 text-[10px] font-mono uppercase tracking-widest text-[var(--muted-fg)] italic">
                    secret · 密文
                  </p>
                  {selectedMeta && (
                    <p className="mt-2 text-xs font-serif leading-snug text-[var(--muted-fg)] break-all">
                      没有 key？去这里申请：
                      <br />
                      {selectedMeta.signupUrl}
                    </p>
                  )}
                </div>
                <div>
                  <input
                    type="password"
                    value={keyEdit ?? ""}
                    onChange={(e) => editKey(e.target.value)}
                    className="field-input font-mono"
                    placeholder={
                      selectedMeta?.hasKey
                        ? "已配置 · 留空保持不变，输入则覆盖"
                        : "粘贴 API Key"
                    }
                  />
                </div>
              </div>
            </section>
          )}

          {/* === 其余通用字段 === */}
          <section className="divide-y divide-[var(--border-light)] border-t-2 border-[var(--ink)] pt-2">
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
          </section>
        </>
      )}

      {/* === 说明 === */}
      <section className="border-t-4 border-[var(--ink)] pt-6">
        <p className="text-sm font-serif italic text-[var(--muted-fg)] leading-relaxed max-w-2xl">
          保存后即时生效——切回「运行」tab 就能用上新选的服务商，无需重启 App。
        </p>
      </section>
    </div>
  );
}
