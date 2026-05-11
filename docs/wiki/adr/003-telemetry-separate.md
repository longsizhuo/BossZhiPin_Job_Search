# ADR-003：LLM telemetry 单独落盘，跟 letters audit log 分离

- **状态**：已采纳
- **日期**：2026-05-12
- **决策人**：longsizhuo
- **相关 commit**：本 PR 引入 `audit/telemetry.py`

## 背景

[`audit/__init__.py`](../../audit/__init__.py) 已经在 `logs/letters.jsonl` 里
存了每次招呼语生成的业务事件（"招呼语 X 被发给了 Y"）。

新增需求：能告诉用户**这一周 / 这一个月跑这个脚本花了多少 LLM 调用费用、平均
延迟、各家 provider 占比**。

直觉的做法是把 telemetry 字段（token 数、cost、latency）塞到 letters.jsonl 里
已有的 record 里。一次落盘，统一查询。

## 为什么没合并

**两边 record 的语义颗粒度不一致**：

1. **letter 跟 LLM 调用不是 1:1**。
   - 一封招呼语可能调多次 LLM（虽然现在没做但未来要做）
   - 一次 LLM 调用可能因为 validate_letter 拦下而没产出 letter（letter 没有，
     LLM 调用记录有）
   - dry-run 里也是同样情况
2. **保留期不一样**。
   - letters 是业务凭证：哪天发了什么招呼语给谁，跟事故 / 招聘者投诉关联，长期保留
   - telemetry 是运营指标：上周成本多少、平均延迟多少，可以按月/季度归档
3. **查询模式不一样**。
   - letters 关注**单条事件**：某条招呼语生成结果、validation reasons、是否发送
   - telemetry 关注**聚合统计**：按 provider/model 拆分的 token sum、cost sum、
     avg_latency

强行合表后写 jq query 会很难看。

## 决策

新增 [`audit/telemetry.py`](../../audit/telemetry.py)，落盘到独立的
`logs/llm_calls.jsonl`，跟 `logs/letters.jsonl` 平级。

API：

```python
# 每次 LLM 调用记一行
record_llm_call(
    provider="deepseek",
    model="deepseek-chat",
    input_tokens=1234,
    output_tokens=256,
    latency_ms=1500,
    letter_len=180,
    ok=True,
)

# 聚合 summary
telemetry_summary(since_records=1000)
# → {"total_calls": ..., "total_cost_cny": ..., "by_provider": {...}}
```

价格表写死在 `PRICING_CNY_PER_M_TOKENS`，未登记的 model 返回成本 0（与其估错
不如留白，让 caller 知道这个 model 还没接进价格表）。

## 命名 / 路径

| 文件 | 内容 |
|---|---|
| `logs/letters.jsonl` | 招呼语审计 |
| `logs/llm_calls.jsonl` | LLM 调用 telemetry |

两个文件都在 `.gitignore` 里，都通过环境变量可改路径（`LETTER_LOG_PATH` /
`BOSS_LLM_TELEMETRY_PATH`）。

## 模块归属

`telemetry` 放在 `audit/` 包下，因为：

- 落盘 + 审计这两个能力天然挨着
- 跟 `audit.validate_letter` / `audit.log_attempt` 共享 `from __future__ import
  annotations` / Path 工具 / JSONL 写入 pattern 这种基础设施
- 包内文件互相 import 也方便（虽然现在不需要）

不放进 `utils/` 是因为 telemetry 不是通用 helper，它有 LLM 特定的 schema（
input_tokens / output_tokens 等）。

## 代价

1. **两个文件需要分别 rotate / 清理**。tail -f 时要分两个 terminal 看。
2. **没法 join**：query "招呼语 X 的具体 token 用量"需要靠 `ts` 时间戳 +
   `provider` 拼接，不严格。但实际不需要这种 join，没成痛点。

## 备选方案

### A. 合并表（已否决）
- ❌ 上文 1-3 三个理由

### B. 用 Prometheus / OTel 上报
- ❌ 对 maintainer 个人项目过度工程
- ❌ 用户不需要装额外组件

### C. SQLite 而不是 JSONL
- ⚠️ 可以查询，但聚合 query 写起来比 jq 还麻烦（pandas 才好用）
- ⚠️ 多一个依赖（虽然 sqlite3 是内置）
- 决定：保持 JSONL，需要时 caller 自己 `pandas.read_json(lines=True)`

## 验证

实测：

```bash
$ uv run python -c "
from audit.telemetry import record_llm_call, telemetry_summary
import json
record_llm_call(provider='deepseek', model='deepseek-chat',
                input_tokens=1500, output_tokens=300, latency_ms=1234, letter_len=180)
print(json.dumps(telemetry_summary(), ensure_ascii=False, indent=2))
"
{
  "total_calls": 1,
  "total_input_tokens": 1500,
  "total_output_tokens": 300,
  "total_cost_cny": 0.0021,
  "by_provider": {
    "deepseek": {
      "calls": 1, "input_tokens": 1500, "output_tokens": 300,
      "cost_cny": 0.0021, "avg_latency_ms": 1234
    }
  }
}
```

## 后续

- 模型变化频繁，`PRICING_CNY_PER_M_TOKENS` 需要每季度对账一次
- 如果 telemetry record 数量大到 jsonl 扫描慢（>1M 行），考虑增量切分到月度
  归档文件（`logs/llm_calls.2026-01.jsonl`）
- 加 `LiteLLM` 之类的 cost-tracking 库被考虑过但拒绝（见 [ADR-002](002-three-providers.md)）
