# FAQ

## 使用

### 这个脚本会被 BOSS 检测到吗？
`nodriver` 已经把绝大部分自动化特征指纹隐藏了，加上我们用持久化 profile（一次
扫码登录之后就走 cookie），BOSS 短期内不会察觉。**但是别滥用**——单日发几百条
是个红线，会触发频控甚至封号。本脚本设计目的是辅助人力，不是替代。

### 三家 provider 我该选哪个？
默认推荐 **DeepSeek**：

| 维度 | DeepSeek | OpenAI | Claude |
|---|---|---|---|
| 单次成本 | ~¥0.002 | ~¥0.02 | ~¥0.04 |
| 中文质量 | 不错 | 不错 | 最好 |
| 招呼语风格 | 略机器 | 中庸 | 自然 |
| 首次跑下载体积 | ~430 MB | 0 | ~430 MB |

预算 100 块跑一个月够发一千多条招呼语，应该够大多数找工作的人用。

### 不想下载 430 MB 的 embedding 模型怎么办？
选 **OpenAI** 路径。它把简历向量化放在 OpenAI 那边的 Vector Store，本地不需要
`sentence-transformers`。代价是单次成本贵一档。

### 招呼语里要不要带学校 / 项目名 / 期望薪资？
建议**只带技术匹配相关的内容**，少自报家门。理由：

- HR 一秒钟看几十条招呼语，先有技术亮点才会点开
- 学校 / 期望薪资这些细节简历里都有，重复说浪费招呼语 800 字预算
- 自报薪资容易被一刀切

可以改 [`models/prompts.py`](../../models/prompts.py) 调 prompt 风格。

### `BOSS_LABEL` 填什么？
留空就好。BOSS 现在新版页面已经没有那种"分类 tag chip"了，留空脚本直接吃推荐
feed。如果你想筛某个具体岗位，去 BOSS 网站手动点一次那个 tag，URL 会变成形如
`/web/geek/jobs?city=xxx&position=yyy` 的，复制对应中文 label 名（比如
"后端开发（成都）"）填进去 —— **完全匹配** BOSS 上的文字。

### 怎么调 prompt？
- 改 [`models/prompts.py`](../../models/prompts.py) 里 `assistant_instructions`
- 先 `DRY_RUN=1 uv run main.py` 跑几条
- `tail -f logs/letters.jsonl | jq '.letter'` 看生成结果
- 不满意继续改，满意了再去掉 `DRY_RUN`

### 招呼语签名怎么避免冗余？
`models/prompts.py` 里 prompt 要求"结尾是 真诚的，{usr_name}"，但 `chat()` 函
数会**自动把 `真诚的，{usr_name}` 这个固定签名再 strip 一次**。这是为了 BOSS
那边自动补签名时不出现重复。

### 我用的是 Azure / 代理网关 / 国内中转
`.env` 里把 `LLM_BASE_URL` 指到你的网关即可，比如
`LLM_BASE_URL=https://your-gateway.com/v1`。代码只认这一个 base_url，不分牌子。

### 想换模型（比如 `gpt-4o-mini` 而不是 `gpt-4o`）？

直接改 `.env` 里的 `LLM_MODEL`：

```bash
echo 'LLM_MODEL=gpt-4o-mini' >> .env
```

## 代码 / 开发

### 我想用一个新端点（比如 Kimi）
**任意 OpenAI 兼容端点本来就能直接跑**——不需要改代码，`.env` 里把
`LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY` 三个填成对应值即可（Kimi 是
`LLM_BASE_URL=https://api.moonshot.cn/v1` + `LLM_MODEL=moonshot-v1-8k`）。

如果你想让它出现在 **GUI 的「常用快捷」下拉**里（只是便利，不是支持范围的限制）：

1. 编辑 [`src/boss_zhipin/providers.py`](../../src/boss_zhipin/providers.py)，在 `LLM_PRESETS` 字典加一行（key、label、base_url、model、signup_url）。
2. 改 [`src/boss_zhipin/audit/telemetry.py`](../../src/boss_zhipin/audit/telemetry.py) 的 `PRICING_CNY_PER_M_TOKENS` 加上对应模型的价格表（想要成本统计准的话）。

### 测试时怎么 mock LLM 调用？
不要 mock。`generate_letter` 已经隔离得很薄了，单测只测 `_build_client` 这种
纯函数；端到端验证靠 `DRY_RUN=1` 真调一次 LLM 看输出。
原因：LLM API 行为变化非常快，靠 mock 测出来的结果跟真实不挂钩。

### 测试时不想真跑 nodriver 怎么办？
**别测**。`finding_jobs.py` 设计上就不期望被 mock —— 它就是一组对真实浏览器的
薄封装。验证靠 `DRY_RUN`：

```bash
DRY_RUN=1 uv run main.py
```

DRY_RUN 模式下浏览器照常起、JD 照常抓、letter 照常生成校验，**只跳过最后那一
下"立即沟通"按钮的点击**。

### 我想看每次 LLM 调用花了多少钱
```bash
uv run python -c "
from audit.telemetry import telemetry_summary
import json
print(json.dumps(telemetry_summary(since_records=1000), ensure_ascii=False, indent=2))
"
```

或者直接：

```bash
tail logs/llm_calls.jsonl | jq '{provider, model, total_tokens, cost_cny, latency_ms}'
```

### 我改了一个函数，怎么知道有没有打破什么？
1. 跑 `uv run pytest tests/ -v`
2. 跑 smoke import check（参见 `.github/workflows/ci.yml` 里那段 `uv run python -c`）
3. 浏览器逻辑改了的话 `DRY_RUN=1 uv run main.py` 至少跑通到 letter 生成

## 概念 / 设计

### 为什么 audit 和 telemetry 分两个 JSONL？
- `letters.jsonl`：业务事件（"招呼语 X 被发给了 Y"）
- `llm_calls.jsonl`：基础设施指标（"调了 Y 次 LLM，花了 Z 元"）

两者的查询模式、保留期、维护责任不一样，强行合并反而难管理。详见
[ADR-003](adr/003-telemetry-separate.md)。

### 为什么不在 audit 落盘前判断 LLM 失败？
因为：

- 网络错误已经被 retry 装饰器吃掉
- 招呼语校验是 `validate_letter` 干的，会拦下抽风的输出
- LLM 返回了内容但是逻辑不对（比如全英文），交给 validate_letter
- 真的崩到上层异常的话，主循环 try-except 会 break 整个 loop

把判断分散在恰当位置比写一个超长的总 try-except 更易调试。

### 为什么 `select_dropdown_option` 这个函数留着，明明 BOSS 现在没有那个 tag chip 了？
作为 fallback。代码逻辑是：

1. 找 tag chip → 没有（新版没了）
2. 找下拉触发器 → 没有
3. fallback：用 BOSS 默认推荐 feed（什么都不做）

万一哪天 BOSS 把 tag UI 加回来，或者你想自定义筛选，这个函数还能用。

## 别的

### 为什么不做 Web UI？
- 命令行加 `.env` 已经够友好（PR #9 之后）
- Web UI 意味着多一层进程间通讯，浏览器 cookie 跨进程更难
- 维护 Web 前端是大坑

但如果你愿意做：先发 issue 讨论方向。Electron 框架的话推荐先看
[CONTRIBUTING.md](../../CONTRIBUTING.md) "Help wanted" 部分。

### 项目会持续维护吗？
当前两个 maintainer：[@longsizhuo](https://github.com/longsizhuo)、
[@TinyAlmond](https://github.com/TinyAlmond)。脚本是个人求职辅助工具，维护节奏
跟"作者们还在找工作 / 还能挤出业余时间"挂钩。
