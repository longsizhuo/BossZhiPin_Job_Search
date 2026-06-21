# 常见故障排查

每个问题都附了**怎么诊断**和**怎么修**，按出现频率由高到低排。

## 1. ❌ 没找到任何 API key

**症状**（`LLM_API_KEY` 没设时 CLI 会列出各家「常用快捷」端点的申请地址然后退出）：

```
❌ 没设置 LLM_API_KEY。
   选一家申请 key，填进 .env 的 LLM_API_KEY（.env.example 有样板）：
     • DeepSeek           https://platform.deepseek.com/api_keys
       LLM_BASE_URL=https://api.deepseek.com  LLM_MODEL=deepseek-chat
     • OpenAI             https://platform.openai.com/api-keys
       ...
```

**修复**：

```bash
cp .env.example .env
# 编辑 .env，至少填 LLM_API_KEY（base_url/model 可用预设默认值）
```

## 2. ❌ 找不到简历文件

**症状**：

```
❌ 找不到简历文件：resume/my_cover.pdf
```

**修复**：

```bash
mkdir -p resume
# 把 PDF 简历放进去，命名 my_cover.pdf
# 或者
echo 'RESUME_PATH=/path/to/your/resume.pdf' >> .env
```

## 3. Chrome 起来后看到的是新建标签页，不是 BOSS

**症状**：脚本输出"页面已稳定 / 检测到已登录"，但 Chrome 视觉上停在新建标签页。

**原因**：Chrome 用持久化 profile 启动时会恢复上次的 tab，控制 tab 被挤到后台。

**修复**：commit [`7dbdf37`](https://github.com/longsizhuo/BossZhiPin_Job_Search/commit/7dbdf37)
之后控制 tab 会单独开在新窗口里。如果你的版本还是老的：

```bash
git pull origin master
```

## 4. 卡在登录页 / 反复跳到新建页

**症状**：脚本输出几次"页面已稳定"后没下文，浏览器在登录页和首页之间反复跳。

**诊断步骤**：

```bash
ls -la chrome_profile/Default/Cookies 2>/dev/null && echo "profile 有 cookie 文件"
# 检查 zhipin 相关 cookie
sqlite3 chrome_profile/Default/Cookies \
  "SELECT host_key, name FROM cookies WHERE host_key LIKE '%zhipin%';"
```

如果只看到 `Hm_lvt_*` / `__a` / `ab_guid` 等跟踪 cookie 但**没有** `wt2` / `bex` /
`__zp_stoken__`，说明你**还没真正完成过一次登录**。

**修复**：彻底关掉所有 Chrome 进程后，跑一次：

```bash
# kill 占用 profile 的 Chrome 后台进程
pkill -f "user-data-dir.*chrome_profile" || true

# 手动开一个 Chrome 用同一个 profile，扫码登录 BOSS
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="$(pwd)/chrome_profile" \
  https://www.zhipin.com/

# 扫码登录成功后退出 Chrome，重跑脚本
DRY_RUN=1 uv run main.py
```

## 5. SessionNotCreatedException / Chrome 起来就崩

**症状**：

```
selenium.common.exceptions.SessionNotCreatedException:
  This version of ChromeDriver only supports Chrome version 148
  Current browser version is 147.0.7727.138
```

**原因**：你用的是旧版仓库代码（依赖 `undetected-chromedriver`），它自带的
chromedriver 跟 Chrome 版本对不齐。

**修复**：

```bash
git pull origin master  # 拉到 nodriver 版本之后这个 error class 不可能再出现
```

## 6. 卡在"页面已稳定 ... /web/geek/jobs"之后

**症状**：登录态识别成功了，但 `select_dropdown_option` 后面卡死。

**原因**：BOSS 把 `/web/geek/job-recommend` 重定向到 `/web/geek/jobs`，新版页面
没有老版本那种"推荐 tag chip"，硬找会卡到超时。

**修复**：commit [`e01c037`](https://github.com/longsizhuo/BossZhiPin_Job_Search/commit/e01c037)
之后所有 xpath 都有显式 timeout + fallback 到"用默认推荐 feed"。`git pull`
拿到最新即可。

也可以**留空** `BOSS_LABEL`（在 `.env` 里），完全跳过 tag 筛选：

```bash
echo 'BOSS_LABEL=' >> .env
```

## 6.1 `get_job_description_by_index` 找不到岗位卡（BOSS 改 DOM 了）

**症状**：日志卡在

```
[get_job_description_by_index] index=1
```

然后 7-12 秒后看到 `xpath 超时: ...` / `没找到列表第 1 个岗位（xpath: ...）`，
连续 5 次都这样，脚本判定"feed 已到底"提前结束。

**原因**：[`website_oper/finding_jobs.py`](../../website_oper/finding_jobs.py)
里那两条岗位卡 / JD 的 XPath 是绝对路径（`//*[@id='wrap']/div[2]/.../ul/li[N]`），
BOSS 改前端 DOM 后会失效。

**诊断**：跑一次 dump 脚本，不用再跟 DevTools console 折腾：

```bash
uv run scripts/dump_boss_page.py
```

会在 `logs/debug/` 落三个文件：

- `page.html` —— BOSS 当前页面整个 outerHTML 快照
- `page.png` —— 视觉截图，确认 nodriver 看到的页面跟你眼里一致
- `selectors.json` —— 自动探测出来的候选岗位卡选择器（按 `data-jobid` /
  class 含关键词 / "≥3 个同 tag 同 class 子元素的容器"几路穷举）

把这三个文件发 issue 或者直接看 `selectors.json` 找新选择器替换
[finding_jobs.py:204](../../website_oper/finding_jobs.py#L204) 那条 XPath。

## 7. 招呼语被 `[BLOCKED]` 拦下

**症状**：

```
[BLOCKED] ['blacklist:'```''] — preview: "您好招聘负责人，```python ..."
```

**原因**：LLM 抽风返回了带代码块 / "As an AI" / 报错字符串的内容。`audit.validate_letter`
保护性地拦了下来 —— 这是设计如此，不是 bug。

**怎么调**：

```bash
tail -f logs/letters.jsonl | jq '{ts, sent, validation_ok, validation_reasons, letter_len, letter: .letter[0:80]}'
```

看到底是哪个规则拦的，按情况：

- LLM 老说"As an AI..." → 强化 prompt（[models/prompts.py](../../models/prompts.py)）
- 招呼语经常超长 → 让 prompt 要求"不超过 200 字"
- 老有英文 → prompt 里加"必须全中文"

## 8. LLM 调用报错 / 招呼语没生成

**症状**：日志里看到端点返回的报错（如 `model not found` / 鉴权失败 / 限流），
招呼语没生成出来。

**原因**：`LLM_*` 三个变量没对齐。最常见是 `LLM_MODEL` 填了一个该端点不存在的
模型名，或者 `LLM_BASE_URL` 跟 key 不是同一家。

**修复**：核对 `.env` 里的三件套——`LLM_BASE_URL` + `LLM_MODEL` + `LLM_API_KEY`
必须是同一家端点的。各家正确值参考 `.env.example` 里的注释，或在 GUI 配置页用
「常用快捷」下拉自动填 base_url + model，只手动粘 key。

```bash
# 例：换成 DeepSeek
echo 'LLM_BASE_URL=https://api.deepseek.com' >> .env
echo 'LLM_MODEL=deepseek-chat' >> .env
```

## 9. 想用日常 Chrome 而不是独立 profile

**症状**：脚本启的 Chrome 跟你日常用的 Chrome 是两个独立窗口，扩展 / 书签 /
登录态全没有。

**这是设计**。理由：

- 用日常 profile 会让脚本拿到你所有 cookie / 扩展 / 浏览历史
- 扩展（AdBlock / 翻译 / 密码管理器）会干扰自动化点击
- 同一时刻 Chrome 不允许两个进程共用一个 profile，必须先 quit 日常 Chrome

如果你**真的**想用日常 profile，**完全 quit 你日常的 Chrome 之后**：

```bash
BOSS_CHROME_PROFILE="$HOME/Library/Application Support/Google/Chrome" \
  uv run main.py
```

⚠️ 改了之后你日常 Chrome 启动也会跟脚本冲突，建议平时不动这个设置。

## 10. job_index 在第 1 个岗位无限循环

**症状**：脚本一直处理 `job_index=1`，不往后走。

**原因**：你用的是 v0.3.0 之前的版本，那里 `# job_index += 1` 被注释掉了。

**修复**：`git pull`。这个 bug 在 commit
[`45136c7`](https://github.com/longsizhuo/BossZhiPin_Job_Search/commit/45136c7) 修复。

## 11. 招呼语生成很慢 / 偶尔超时

**症状**：每次 letter 生成等很久，偶尔抛 `httpx.ReadTimeout`。

**原因**：DeepSeek / OpenAI API 偶发 5xx 或网络抖动。

**修复**：项目内置了指数退避重试（[utils/retry.py](../../utils/retry.py)）。
如果想调宽：

```bash
# .env
BOSS_RETRY_MAX_ATTEMPTS=5      # 默认 3
BOSS_RETRY_BASE_DELAY=4.0      # 默认 2.0
BOSS_RETRY_MAX_DELAY=60.0      # 默认 30.0
```

## 12. 想看一段时间内的 LLM 花了多少钱

**怎么做**：

```bash
uv run python -c "
from audit.telemetry import telemetry_summary
import json
print(json.dumps(telemetry_summary(since_records=1000), ensure_ascii=False, indent=2))
"
```

会输出形如：

```json
{
  "total_calls": 87,
  "total_input_tokens": 145000,
  "total_output_tokens": 12300,
  "total_cost_cny": 0.51,
  "by_provider": {
    "deepseek": {"calls": 87, "cost_cny": 0.51, "avg_latency_ms": 1234}
  }
}
```

## 13. 怎么彻底重置脚本状态

```bash
rm -rf chrome_profile/   # 删 profile（cookie 一起没）
rm -rf vectorstores/     # 删向量库（下次跑会重新 embed）
rm -rf logs/             # 删历史 audit
```

然后重跑 `DRY_RUN=1 uv run main.py`。

## 14. 桌面 App（macOS）启动即崩："Check with the developer to make sure BOSS Zhipin Helper works with this version of macOS"

v0.3.1 的 .app 在 macOS 26+ 上会启动即崩，弹这个系统崩溃对话框。原因：ad-hoc
签名默认带 hardened runtime，library validation 拒载 bundle 内 linker-signed 的
`libpython3.13.dylib`。崩溃报告（`~/Library/Logs/DiagnosticReports/boss-zhipin-*.ips`）
里能看到：

```
Library not loaded: @rpath/libpython3.13.dylib
... (non-platform) have different Team IDs
```

**修复**：升级到 v0.3.2+（签名已注入 `com.apple.security.cs.disable-library-validation`
entitlement，见 `src-tauri/entitlements.plist`）。

不想升级的临时绕法——重签去掉 hardened runtime flag：

```bash
codesign --force --deep -s - "/Applications/BOSS Zhipin Helper.app"
```

## 还是不行？

提 issue：https://github.com/longsizhuo/BossZhiPin_Job_Search/issues

issue 里附上：

1. 哪一步卡的 / 报什么错（粘控制台输出）
2. `python --version` / `uv --version` / Chrome 版本
3. macOS / Linux / Windows，OS 版本
4. 你的 `.env` 里设了哪些 key（**不要粘 key 值**，只列变量名）
