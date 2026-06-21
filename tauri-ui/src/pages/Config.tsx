import { useEffect, useState } from "react";
import { ipc, type EnvField, type LlmConfig } from "../lib/ipc";

// 配置页：.env 编辑
// monochrome 设计：editorial 表单 —— 每个字段 key 用反色 mono 标签
//
// 顶部「AI 端点」段：通用 OpenAI 兼容端点 = Base URL + Key + Model。
// 一个可选的「常用快捷」下拉自动填 base_url + model（默认「自定义」），
// 支持任意端点——DeepSeek/OpenAI/Claude/百炼/GLM/豆包/Kimi/本地 Ollama…
// 都是同一条路，列表只是糖，不是限制。下面是其余通用字段。
const CUSTOM = ""; // 下拉里「自定义」的值

export default function ConfigPage() {
  const [fields, setFields] = useState<EnvField[]>([]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // LLM 端点段
  const [llmCfg, setLlmCfg] = useState<LlmConfig | null>(null);
  const [preset, setPreset] = useState<string>(CUSTOM);
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  // null = 用户没动 key 框（保存时不传 key，不覆盖已存的）
  const [keyEdit, setKeyEdit] = useState<string | null>(null);
  // 明文/密文切换：粘贴 key 后能核对一眼，避免带错空格/漏字符跑到一半才报 401
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [{ fields }, cfg] = await Promise.all([
        ipc.getEnvFields(),
        ipc.getLlmConfig(),
      ]);
      setFields(fields);
      setEdits({});
      setLlmCfg(cfg);
      setBaseUrl(cfg.baseUrl);
      setModel(cfg.model);
      setKeyEdit(null);
      // 按 baseUrl 匹配预设来高亮下拉；匹配不上就是「自定义」
      const match = cfg.presets.find((p) => p.baseUrl === cfg.baseUrl);
      setPreset(match ? match.name : CUSTOM);
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

  function pickPreset(name: string) {
    setSaved(false);
    setPreset(name);
    if (name === CUSTOM) return; // 自定义：保留用户当前填的
    const p = llmCfg?.presets.find((x) => x.name === name);
    if (p) {
      setBaseUrl(p.baseUrl);
      setModel(p.model);
    }
  }

  function editBaseUrl(v: string) {
    setSaved(false);
    setBaseUrl(v);
    setPreset(CUSTOM); // 手改即视为自定义
  }
  function editModel(v: string) {
    setSaved(false);
    setModel(v);
    setPreset(CUSTOM);
  }
  function editKey(v: string) {
    setSaved(false);
    setKeyEdit(v);
  }

  const llmDirty =
    llmCfg !== null &&
    (baseUrl !== llmCfg.baseUrl || model !== llmCfg.model || keyEdit !== null);
  const dirty = Object.keys(edits).length > 0 || llmDirty;

  async function save() {
    setSaving(true);
    setError(null);
    try {
      if (llmDirty) {
        await ipc.setLlmConfig(baseUrl.trim(), model.trim(), keyEdit ?? "");
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

  const selectedPreset = llmCfg?.presets.find((p) => p.name === preset);

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
          {saved && !dirty && <span className="badge-invert">✓ Saved</span>}
          {dirty && <span className="badge-outline italic">unsaved · 未保存</span>}
          <button onClick={save} disabled={!dirty || saving} className="btn">
            {saving ? "保存中..." : "保存 →"}
          </button>
        </div>
      </section>

      {/* === 错误带 === */}
      {error && (
        <div className="border-2 border-[var(--ink)] p-4 flex items-start gap-3">
          <span className="badge-invert flex-shrink-0">ERROR</span>
          <pre className="text-sm font-mono whitespace-pre-wrap flex-1">{error}</pre>
        </div>
      )}

      {loading ? (
        <div className="font-mono text-sm text-[var(--muted-fg)] italic">Loading...</div>
      ) : (
        <>
          {/* === AI 端点：base_url + key + model === */}
          {llmCfg && (
            <section className="space-y-5">
              <div>
                <label className="field-label">AI 端点 / Endpoint</label>
                <p className="mt-1 text-xs font-mono text-[var(--muted-fg)] italic">
                  任意 OpenAI 兼容端点都行 —— 选个常用快捷自动填，或「自定义」手填
                </p>
              </div>

              {/* 常用快捷：默认「自定义」，选了自动填 base_url + model */}
              <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-4 md:gap-10 items-center">
                <div className="font-mono text-xs uppercase tracking-widest text-[var(--muted-fg)]">
                  常用快捷 · Preset
                </div>
                <select
                  value={preset}
                  onChange={(e) => pickPreset(e.target.value)}
                  className="field-input font-mono"
                >
                  <option value={CUSTOM}>自定义 / Custom</option>
                  {llmCfg.presets.map((p) => (
                    <option key={p.name} value={p.name}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Base URL */}
              <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-4 md:gap-10 items-start">
                <div className="font-mono text-xs uppercase tracking-widest bg-[var(--ink)] text-[var(--paper)] inline-block px-2 py-1 self-start">
                  LLM_BASE_URL
                </div>
                <input
                  type="text"
                  value={baseUrl}
                  onChange={(e) => editBaseUrl(e.target.value)}
                  className="field-input font-mono"
                  placeholder="留空 = OpenAI 默认端点；如 https://api.deepseek.com"
                />
              </div>

              {/* Model */}
              <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-4 md:gap-10 items-start">
                <div className="font-mono text-xs uppercase tracking-widest bg-[var(--ink)] text-[var(--paper)] inline-block px-2 py-1 self-start">
                  LLM_MODEL
                </div>
                <input
                  type="text"
                  value={model}
                  onChange={(e) => editModel(e.target.value)}
                  className="field-input font-mono"
                  placeholder="如 deepseek-chat / gpt-4o / glm-4-plus"
                />
              </div>

              {/* API Key */}
              <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-4 md:gap-10 items-start">
                <div>
                  <div className="font-mono text-xs uppercase tracking-widest bg-[var(--ink)] text-[var(--paper)] inline-block px-2 py-1">
                    LLM_API_KEY
                  </div>
                  <p className="mt-2 text-[10px] font-mono uppercase tracking-widest text-[var(--muted-fg)] italic">
                    secret · 密文
                  </p>
                  {selectedPreset && (
                    <p className="mt-2 text-xs font-serif leading-snug text-[var(--muted-fg)] break-all">
                      申请：{selectedPreset.signupUrl}
                    </p>
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <input
                      type={showKey ? "text" : "password"}
                      value={keyEdit ?? ""}
                      onChange={(e) => editKey(e.target.value)}
                      className="field-input font-mono flex-1"
                      placeholder={
                        llmCfg.hasKey ? "已配置 · 留空保持不变，输入则覆盖" : "粘贴 API Key"
                      }
                    />
                    <button
                      type="button"
                      onClick={() => setShowKey((v) => !v)}
                      className="btn-ghost text-xs flex-shrink-0"
                      aria-label={showKey ? "隐藏 key" : "显示 key"}
                    >
                      {showKey ? "隐藏" : "显示"}
                    </button>
                  </div>
                  {/* 选了预设但还没配 key：提示去填，别等点开始才发现没 key */}
                  {selectedPreset && !llmCfg.hasKey && !keyEdit && (
                    <p className="mt-2 text-xs font-mono text-[var(--muted-fg)] italic">
                      选了 {selectedPreset.label}，记得在上面粘贴它的 API key 再保存。
                    </p>
                  )}
                </div>
              </div>
            </section>
          )}

          {/* === 其余通用字段 === */}
          <section className="divide-y divide-[var(--border-light)] border-t-2 border-[var(--ink)] pt-2">
            {fields.map((f) => (
              <div key={f.key} className="py-6 grid grid-cols-1 md:grid-cols-[200px_1fr] gap-4 md:gap-10 items-start">
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
                <div>
                  <input
                    type={f.isSecret ? "password" : "text"}
                    value={valueFor(f.key, f.value)}
                    onChange={(e) => setField(f.key, e.target.value)}
                    className="field-input font-mono"
                    placeholder={f.isSecret ? "已设 · 留空保存即视为删除" : ""}
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
          保存后即时生效——切回「运行」tab 就能用上新端点，无需重启 App。
        </p>
      </section>
    </div>
  );
}
