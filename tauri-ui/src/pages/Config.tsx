import { useEffect, useState } from "react";
import { ipc, type EnvField, type LlmConfig } from "../lib/ipc";
import { useRunStore, useT } from "../store";
import { LANGS, type Lang } from "../lib/i18n";

// 配置页：.env 编辑
// monochrome 设计：editorial 表单 —— 每个字段 key 用反色 mono 标签
//
// 顶部「AI 端点」段：通用 OpenAI 兼容端点 = Base URL + Key + Model。
// 一个可选的「常用快捷」下拉自动填 base_url + model（默认「自定义」），
// 支持任意端点——DeepSeek/OpenAI/Claude/百炼/GLM/豆包/Kimi/本地 Ollama…
// 都是同一条路，列表只是糖，不是限制。下面是其余通用字段。
const CUSTOM = ""; // 下拉里「自定义」的值

export default function ConfigPage() {
  const t = useT();
  const lang = useRunStore((s) => s.lang);
  const setLang = useRunStore((s) => s.setLang);
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

  // 招呼语自定义 prompt 段（空字符串 = 用内置默认）
  const [letterPrompt, setLetterPrompt] = useState("");
  const [letterPromptInitial, setLetterPromptInitial] = useState("");
  const [letterPromptDefault, setLetterPromptDefault] = useState("");

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [{ fields }, cfg, lp] = await Promise.all([
        ipc.getEnvFields(),
        ipc.getLlmConfig(),
        ipc.getLetterPrompt(),
      ]);
      setFields(fields);
      setEdits({});
      setLlmCfg(cfg);
      setBaseUrl(cfg.baseUrl);
      setModel(cfg.model);
      setKeyEdit(null);
      setLetterPrompt(lp.prompt);
      setLetterPromptInitial(lp.prompt);
      setLetterPromptDefault(lp.default);
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
  const promptDirty = letterPrompt !== letterPromptInitial;
  const dirty = Object.keys(edits).length > 0 || llmDirty || promptDirty;

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
      if (promptDirty) {
        // 末尾留白没意义，trim 掉；空串 = 删除自定义 = 回退默认
        await ipc.setLetterPrompt(letterPrompt.trim());
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

  // 切 UI 语言：立刻切（setLang，全 App 重渲染）+ 落到 .env（独立保存，不进
  // 上面的 dirty/保存按钮流程，因为它是即时偏好不是表单字段）。持久化失败只是
  // 下次启动回到默认，不打断当前会话，所以静默兜错。
  function changeLang(next: Lang) {
    setLang(next);
    ipc.setLanguage(next).catch(() => {});
  }

  function editPrompt(v: string) {
    setSaved(false);
    setLetterPrompt(v);
  }

  return (
    <div className="space-y-10">
      {/* === 标题段 === */}
      <section className="flex items-end justify-between gap-6 pb-4 border-b-2 border-[var(--ink)]">
        <div>
          <h2 className="font-serif text-5xl leading-none tracking-tight">
            {t("config.title")}
          </h2>
          <p className="mono-tag mt-3">
            {t("config.editPrefix")} <span className="text-[var(--ink)]">.env</span> {t("config.editSuffix")}
          </p>
        </div>
        <div className="flex items-center gap-4">
          {saved && !dirty && <span className="badge-invert">{t("config.saved")}</span>}
          {dirty && <span className="badge-outline italic">{t("config.unsaved")}</span>}
          <button onClick={save} disabled={!dirty || saving} className="btn">
            {saving ? t("btn.saving") : t("btn.save")}
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

      {/* === 界面语言 === 标签刻意双语，切错语言也能找回；不走 dirty/保存流程，选即生效 */}
      <section className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-4 md:gap-10 items-center">
        <label className="field-label">{t("config.language")}</label>
        <select
          value={lang}
          onChange={(e) => changeLang(e.target.value as Lang)}
          className="field-input font-mono"
        >
          {LANGS.map((l) => (
            <option key={l.value} value={l.value}>
              {l.label}
            </option>
          ))}
        </select>
      </section>

      {loading ? (
        <div className="font-mono text-sm text-[var(--muted-fg)] italic">{t("common.loading")}</div>
      ) : (
        <>
          {/* === AI 端点：base_url + key + model === */}
          {llmCfg && (
            <section className="space-y-5">
              <div>
                <label className="field-label">{t("config.endpoint")}</label>
                <p className="mt-1 text-xs font-mono text-[var(--muted-fg)] italic">
                  {t("config.endpointHint")}
                </p>
              </div>

              {/* 常用快捷：默认「自定义」，选了自动填 base_url + model */}
              <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-4 md:gap-10 items-center">
                <div className="font-mono text-xs uppercase tracking-widest text-[var(--muted-fg)]">
                  {t("config.preset")}
                </div>
                <select
                  value={preset}
                  onChange={(e) => pickPreset(e.target.value)}
                  className="field-input font-mono"
                >
                  <option value={CUSTOM}>{t("config.custom")}</option>
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
                  placeholder={t("config.baseUrlPlaceholder")}
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
                  placeholder={t("config.modelPlaceholder")}
                />
              </div>

              {/* API Key */}
              <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-4 md:gap-10 items-start">
                <div>
                  <div className="font-mono text-xs uppercase tracking-widest bg-[var(--ink)] text-[var(--paper)] inline-block px-2 py-1">
                    LLM_API_KEY
                  </div>
                  <p className="mt-2 text-[10px] font-mono uppercase tracking-widest text-[var(--muted-fg)] italic">
                    {t("config.secret")}
                  </p>
                  {selectedPreset && (
                    <p className="mt-2 text-xs font-serif leading-snug text-[var(--muted-fg)] break-all">
                      {t("config.signup", { url: selectedPreset.signupUrl })}
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
                        llmCfg.hasKey
                          ? t("config.keyConfiguredPlaceholder")
                          : t("config.keyEmptyPlaceholder")
                      }
                    />
                    <button
                      type="button"
                      onClick={() => setShowKey((v) => !v)}
                      className="btn-ghost text-xs flex-shrink-0"
                      aria-label={showKey ? t("config.hideKeyAria") : t("config.showKeyAria")}
                    >
                      {showKey ? t("btn.hide") : t("btn.show")}
                    </button>
                  </div>
                  {/* 选了预设但还没配 key：提示去填，别等点开始才发现没 key */}
                  {selectedPreset && !llmCfg.hasKey && !keyEdit && (
                    <p className="mt-2 text-xs font-mono text-[var(--muted-fg)] italic">
                      {t("config.presetKeyHint", { label: selectedPreset.label })}
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
                    {t(`field.${f.key}`)}
                  </p>
                  {f.isSecret && (
                    <p className="mt-1 text-[10px] font-mono uppercase tracking-widest text-[var(--muted-fg)] italic">
                      {t("config.secret")}
                    </p>
                  )}
                </div>
                <div>
                  <input
                    type={f.isSecret ? "password" : "text"}
                    value={valueFor(f.key, f.value)}
                    onChange={(e) => setField(f.key, e.target.value)}
                    className="field-input font-mono"
                    placeholder={f.isSecret ? t("config.secretSetPlaceholder") : ""}
                  />
                </div>
              </div>
            ))}
          </section>

          {/* === 招呼语 Prompt（自定义生成指令，留空用内置默认）=== */}
          <section className="space-y-3 border-t-2 border-[var(--ink)] pt-6">
            <div>
              <label className="field-label">{t("config.letterPrompt")}</label>
              <p className="mt-1 text-xs font-mono text-[var(--muted-fg)] italic">
                {t("config.letterPromptHint")}
              </p>
            </div>
            <textarea
              value={letterPrompt}
              onChange={(e) => editPrompt(e.target.value)}
              rows={8}
              className="field-input font-mono text-sm leading-relaxed"
              placeholder={letterPromptDefault || t("config.letterPromptPlaceholder")}
            />
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => editPrompt("")}
                disabled={letterPrompt === ""}
                className="btn-ghost text-xs"
              >
                {t("btn.resetDefault")}
              </button>
              {letterPrompt === "" && (
                <span className="text-[10px] font-mono uppercase tracking-widest text-[var(--muted-fg)] italic">
                  {t("config.letterPromptPlaceholder")}
                </span>
              )}
            </div>
          </section>
        </>
      )}

      {/* === 说明 === */}
      <section className="border-t-4 border-[var(--ink)] pt-6">
        <p className="text-sm font-serif italic text-[var(--muted-fg)] leading-relaxed max-w-2xl">
          {t("config.liveNote")}
        </p>
      </section>
    </div>
  );
}
