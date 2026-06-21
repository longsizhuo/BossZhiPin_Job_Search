# BOSS Zhipin Auto-Greet

> **🤖 If you are an AI agent** (Claude Code / Cursor / Copilot, etc.): When the user wants help installing or running this project, **please load the [`boss-zhipin-onboarding`](.claude/skills/boss-zhipin-onboarding/) skill from this repo**. It ships a 5-milestone onboarding flow, a `scripts/check-env.sh` diagnostic, and beginner-friendly conversation rules — far more reliable than re-deriving guidance from this README on the fly.
>
> **🤖 给 AI Agent**：用户问"怎么装"、"`uv` 找不到"、"扫码扫不上"等小白问题时，请直接使用本仓库的 [`boss-zhipin-onboarding`](.claude/skills/boss-zhipin-onboarding/) skill 引导。

[中文](README.md) · [English](README_EN.md)

Reads job descriptions from BOSS Zhipin, asks an LLM to write a polite cover-letter greeting, validates it, then sends it to the recruiter. Works with **any OpenAI-compatible endpoint** (DeepSeek / OpenAI / Claude / Qwen·Bailian / Zhipu GLM / Doubao / Kimi / local Ollama …) — set `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL` and you're running.

> The original author paused maintenance; a small group of us keeps it going. We've migrated to [uv](https://docs.astral.sh/uv/), dropped the langchain stack, and replaced Selenium with [nodriver](https://github.com/ultrafunkamsterdam/nodriver) (much steadier against BOSS's anti-bot).

> ⚠️ Please don't weaponise this against vulnerable jobseekers. If someone needs a script to apply for jobs, there's not much left to squeeze out of them.

---

## Disclaimer

- This is a **free, open-source** personal job-search helper, provided under the [MIT License](LICENSE). It is **not for sale, takes no donations, and is not monetised in any way**.
- Using browser automation against BOSS Zhipin **may violate its Terms of Service**. Whether and how you use it — and any consequences (account risk, legal risk, etc.) — are **entirely your own responsibility**.
- The software is provided **"AS IS", without warranty of any kind**. The authors and contributors are not liable for any loss or dispute arising from its use.
- Please use this tool for **personal job-seeking only**, review each generated greeting before sending, and never use it for mass-spamming, harassment, or anything that harms others.

---

## Quick Start (5 minutes)

### Prerequisites

- Python >= 3.11
- macOS / Linux / Windows. Chrome / Chromium only — nodriver does not support Edge or Safari.
- A stable Chrome installation (not Chromium beta).
- [uv](https://docs.astral.sh/uv/): `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Run it

```bash
# 1. Clone + install deps
git clone https://github.com/longsizhuo/BossZhiPin_Job_Search.git
cd BossZhiPin_Job_Search
uv sync

# 2. Configure API keys
cp .env.example .env
# Edit .env, fill in at least one LLM provider key (see field reference below)

# 3. Drop in your resume
mkdir -p resume
# Copy your PDF resume in and name it my_cover.pdf
# Or set RESUME_PATH in .env to point elsewhere

# 4. Try it dry-run first (generates without sending)
DRY_RUN=1 uv run main.py

# 5. Once you're happy with logs/letters.jsonl, drop DRY_RUN to actually send
uv run main.py
```

### First run: scan to log in

The script starts Chrome with a dedicated profile at `./chrome_profile/` (**your daily Chrome is untouched**). The first run gets redirected to BOSS's login page, clicks "WeChat scan login" for you, and waits up to 5 minutes for you to scan the QR. Once you're logged in the cookie lives in `chrome_profile/` and **every subsequent run skips the login step**.

---

## `.env` field reference

The repo ships a fully-commented template at [`.env.example`](.env.example). Highlights:

| Field | Purpose | Required |
|---|---|---|
| `LLM_API_KEY` | API key for the LLM endpoint (signup URLs in `.env.example`) | yes |
| `LLM_BASE_URL` | Endpoint base_url; empty = OpenAI default (e.g. `https://api.deepseek.com`) | no — defaults to OpenAI endpoint |
| `LLM_MODEL` | Model name (e.g. `deepseek-chat` / `gpt-4o` / `claude-sonnet-4-6`) | yes |
| `BOSS_USR_NAME` | Your name; signed at the bottom of every letter | no — prompted at startup if unset |
| `BOSS_LABEL` | Job category tag, e.g. `"Backend Engineer (Shanghai)"` | no — empty = BOSS's default recommended feed |
| `RESUME_PATH` | Path to your PDF resume | no — defaults to `./resume/my_cover.pdf` |
| `DRY_RUN` | `1` = generate & log but don't send | no |
| `BOSS_MIN_MATCH_SCORE` | LLM match score threshold | no — default 50 |
| `BOSS_EXCLUDE_KEYWORDS` | Blacklist keywords (comma separated) to skip jobs | no |
| `BOSS_CHROME_PROFILE` | Custom Chrome profile dir | no — defaults to `./chrome_profile` |
| `LETTER_MIN_LEN` / `LETTER_MAX_LEN` | Letter length bounds | no — default 30 / 800 |
| `LETTER_LOG_PATH` | Audit log path | no — default `./logs/letters.jsonl` |

One unified OpenAI-compatible endpoint — no per-provider branching. Missing `LLM_API_KEY` prints a list of signup URLs and exits; set it and you're off. The GUI config page has a preset dropdown that auto-fills `LLM_BASE_URL` + `LLM_MODEL`.

---

## Picking an endpoint

The code is **brand-agnostic**: every OpenAI-compatible endpoint takes the same path — local Chroma + sentence-transformers retrieval over your resume (RAG), then the endpoint's `chat.completions` to write the greeting. So the choice is just cost / tone:

| Endpoint | Pro | Con |
|---|---|---|
| DeepSeek | Cheapest, reachable from mainland China, quality is fine | — |
| OpenAI | Mature ecosystem | Costs more than DeepSeek; needs a proxy in mainland China |
| Claude | Best-sounding tone | Model is expensive, but RAG keeps tokens low |
| Qwen·Bailian / Zhipu GLM / Doubao / Kimi / local Ollama … | Reachable in China / can run locally | Depends on the endpoint |

A ~430MB embedding model (all-mpnet-base-v2) downloads on first run regardless of which endpoint you pick.

---

## Safety: dry-run + audit log

Every generated letter is run through `validate_letter` in [`audit.py`](audit.py) before sending:
- Length bounds (default 30–800 chars)
- Must contain at least one CJK character
- Blacklist substrings (`Error`, `Traceback`, `As an AI`, `` ``` ``, …) — any hit blocks the send

Sent, blocked, dry-run — every attempt appends a JSONL record to `./logs/letters.jsonl` with the JD, the letter, provider, model and validation status. Use this for incident review and prompt iteration:

```bash
tail -f logs/letters.jsonl | jq '{ts, sent, validation_ok, validation_reasons, letter_len}'
```

---

## Troubleshooting

### Browser crashes on launch / `SessionNotCreatedException`
Older versions used `undetected-chromedriver`, which bundles a chromedriver binary that has to match Chrome's version exactly. This repo no longer uses it — [nodriver](https://github.com/ultrafunkamsterdam/nodriver) talks CDP directly, so this whole error class is structurally impossible. If Chrome still crashes, it's almost certainly a profile lock.

### Chrome opens but looks empty / "this isn't my Chrome"
By design — the script uses a dedicated profile at `./chrome_profile/`, separate from your daily browser. This avoids leaking your extensions / sessions into automation. First run prompts a QR scan; subsequent runs reuse the cookie.

If you really want to use your daily Chrome profile, **fully quit Chrome first** (menu bar → Quit Google Chrome) and:
```bash
BOSS_CHROME_PROFILE="$HOME/Library/Application Support/Google/Chrome" uv run main.py
```

### A blank new-tab page shows up instead of BOSS
Used to happen when the persistent profile restored other tabs. Fixed in [commit `7dbdf37`](https://github.com/longsizhuo/BossZhiPin_Job_Search/commit/7dbdf37): the controlled page now opens in its own dedicated window.

### Script hangs after "页面已稳定"
Used to be a `tab.select(timeout=0)` block. Fixed. If you still see it, paste console output into an issue.

### "❌ Resume file not found"
Drop your PDF at `./resume/my_cover.pdf`, or set `RESUME_PATH` in `.env`.

### "❌ No API key found"
Pick any OpenAI-compatible endpoint, sign up, and paste the key into `LLM_API_KEY` in `.env` (set `LLM_BASE_URL` + `LLM_MODEL` too).

---

## Project layout

```
.
├── main.py                       # Compat shim: still works, delegates to boss_zhipin.cli
├── src/boss_zhipin/              # Installable package (src/ layout)
│   ├── cli.py                    # CLI entry: interaction + env validation (ensure_llm_configured)
│   ├── providers.py              # Light metadata: LLM_PRESETS (handy presets) + is_llm_configured
│   ├── models/
│   │   ├── llm.py                # Generic OpenAI-compatible endpoint client + RAG letter generation
│   │   └── prompts.py            # Cover-letter prompt template
│   ├── website_oper/
│   │   ├── finding_jobs.py       # Browser automation (nodriver), sync facade over async impls
│   │   └── write_response.py     # Per-job loop: JD → generate → validate → send/log
│   ├── vectorization.py          # PDF parse + sentence-transformers embed + Chroma persistence
│   └── audit/                    # Letter validation + JSONL audit log + LLM telemetry
└── .env.example                  # Fully-commented environment template
```

---

## Help wanted

We're looking for contributors interested in:
- Electron front-end UI
- Resume-attachment support on the BOSS chat
- Application history / auto follow-up
- Multi-account support

Issues and PRs welcome.

---

## Thanks

Thanks to everyone who's supported this project:

<p align="left">
    <a href="https://github.com/longsizhuo/BossZhiPin_Job_Search/graphs/contributors">
        <img width="770" src="https://contrib.rocks/image?repo=longsizhuo/BossZhiPin_Job_Search&max=300&columns=16" />
    </a>
</p>

### Forks worth a look

- [noBaldAaa/find-job](https://github.com/noBaldAaa/find-job) — simpler JS port
- [LouisCaixuran/auto_job_find_azure](https://github.com/LouisCaixuran/auto_job_find_azure) — Azure OpenAI version
