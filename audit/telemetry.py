"""LLM 调用 telemetry —— 落盘每次 LLM 调用的成本 / 时长 / token 数。

为什么单独搞这个：
    [audit/__init__.py](audit/__init__.py) 里的 ``log_attempt`` 记的是
    "招呼语生成 → 是否通过校验 → 是否发送"，是业务侧的审计。
    本模块记的是"调了哪家 LLM、花了多少钱、多久回来"，是基础设施侧的指标。
    两者目的不同，故分开存（``logs/llm_calls.jsonl`` vs ``logs/letters.jsonl``）。

设计要点：
- 调一次 LLM 一行 JSON，append-only，不需要 lock（jsonl 容忍并发追加）。
- 价格表写死在 ``PRICING_CNY_PER_M_TOKENS`` —— 各家 provider 公开计价口径不
  统一，但都换算到 ¥/1M tokens 这个粒度。价格表脏数据宁可没有也别瞎填，
  没匹配上时 ``estimate_cost_cny`` 返回 0.0 而不是估错。
- 落盘失败不能阻断业务 —— 只 ``log.warning``，调用方拿到 record 字典正常返回。

事件 schema：

.. code-block:: json

    {
      "ts": "2026-05-12T03:45:00+08:00",
      "provider": "deepseek",
      "model": "deepseek-chat",
      "input_tokens": 1234,
      "output_tokens": 256,
      "total_tokens": 1490,
      "latency_ms": 1234,
      "cost_cny": 0.001789,
      "letter_len": 180,
      "ok": true,
      "error": null
    }
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# 落盘路径，跟 letters.jsonl 并列；BOSS_LLM_TELEMETRY_PATH 可覆盖
TELEMETRY_PATH = Path(
    os.getenv("BOSS_LLM_TELEMETRY_PATH", "./logs/llm_calls.jsonl")
)

# 各家 provider 公开价格（CNY / 1M tokens）。来源：
#   DeepSeek    https://api-docs.deepseek.com/quick_start/pricing
#   OpenAI      https://openai.com/api/pricing/ （按 1 USD ≈ 7.1 CNY）
#   Anthropic   https://www.anthropic.com/pricing （按 1 USD ≈ 7.1 CNY）
# 价格会变，数字过期不影响功能（只是 cost_cny 估算偏差），更新时改这里就行。
PRICING_CNY_PER_M_TOKENS: dict[str, dict[str, float]] = {
    # DeepSeek
    "deepseek-chat": {"input": 1.0, "output": 2.0},
    "deepseek-reasoner": {"input": 3.1, "output": 6.2},
    # OpenAI
    "gpt-4o": {"input": 17.0, "output": 70.0},
    "gpt-4o-mini": {"input": 1.1, "output": 4.3},
    "gpt-4-turbo": {"input": 70.0, "output": 220.0},
    "gpt-5": {"input": 9.0, "output": 70.0},
    # Anthropic Claude
    "claude-sonnet-4-6": {"input": 21.0, "output": 105.0},
    "claude-opus-4-7": {"input": 105.0, "output": 525.0},
    "claude-haiku-4-5-20251001": {"input": 6.0, "output": 30.0},
}


def estimate_cost_cny(model: str, input_tokens: int, output_tokens: int) -> float:
    """按公开价格估算单次 LLM 调用成本（CNY）。

    未在 ``PRICING_CNY_PER_M_TOKENS`` 里登记的 model 返回 0.0 —— 与其估错不如
    留白，让 caller 知道这个 model 还没接进价格表。
    """
    pricing = PRICING_CNY_PER_M_TOKENS.get(model)
    if not pricing:
        return 0.0
    return round(
        input_tokens / 1_000_000 * pricing["input"]
        + output_tokens / 1_000_000 * pricing["output"],
        6,
    )


def record_llm_call(
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    letter_len: int = 0,
    ok: bool = True,
    error: str | None = None,
) -> dict[str, Any]:
    """记录一次 LLM 调用，返回最终落盘的 record 字典。

    ``letter_len`` 是这次调用产出的招呼语字符数（不是 token，是 ``len(text)``），
    方便后续按"长度分布"做粗剖，不必再 re-tokenize。

    落盘失败只 ``log.warning`` 不抛 —— telemetry 不能挡业务路径。
    """
    cost = estimate_cost_cny(model, input_tokens, output_tokens)
    record: dict[str, Any] = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "provider": provider,
        "model": model,
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "total_tokens": int((input_tokens or 0) + (output_tokens or 0)),
        "latency_ms": int(latency_ms),
        "cost_cny": cost,
        "letter_len": int(letter_len),
        "ok": bool(ok),
        "error": error,
    }
    try:
        TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TELEMETRY_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001
        log.warning("LLM telemetry 落盘失败: %s", e)
    return record


def read_telemetry(since: int = 200) -> list[dict[str, Any]]:
    """读 ``TELEMETRY_PATH`` 末尾 ``since`` 行（最近 N 条）。文件不存在返回 []。"""
    if not TELEMETRY_PATH.exists():
        return []
    try:
        with open(TELEMETRY_PATH, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:  # noqa: BLE001
        log.warning("读 LLM telemetry 失败: %s", e)
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-since:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            # 损坏的行跳过，不让整批数据废掉
            continue
    return out


def telemetry_summary(since_records: int = 1000) -> dict[str, Any]:
    """对最近 ``since_records`` 条记录做聚合：

    返回字典含 ``total_calls / total_input_tokens / total_output_tokens /
    total_cost_cny`` 全局值，加 ``by_provider`` 子字典按 provider 拆分。

    没有数据时返回的字典所有数值字段为 0，``by_provider`` 为空字典 —— caller
    不用判 None。
    """
    records = read_telemetry(since=since_records)
    if not records:
        return {
            "total_calls": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost_cny": 0.0,
            "by_provider": {},
        }

    total_calls = len(records)
    total_input = sum(r.get("input_tokens", 0) for r in records)
    total_output = sum(r.get("output_tokens", 0) for r in records)
    total_cost = round(sum(r.get("cost_cny", 0) for r in records), 4)

    by_provider: dict[str, dict[str, Any]] = {}
    for r in records:
        prov = r.get("provider", "unknown")
        d = by_provider.setdefault(prov, {
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_cny": 0.0,
            "avg_latency_ms": 0,
            "_lat_sum": 0,
        })
        d["calls"] += 1
        d["input_tokens"] += r.get("input_tokens", 0)
        d["output_tokens"] += r.get("output_tokens", 0)
        d["cost_cny"] = round(d["cost_cny"] + r.get("cost_cny", 0), 4)
        d["_lat_sum"] += r.get("latency_ms", 0)
    for d in by_provider.values():
        if d["calls"]:
            d["avg_latency_ms"] = d["_lat_sum"] // d["calls"]
        d.pop("_lat_sum", None)

    return {
        "total_calls": total_calls,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cost_cny": total_cost,
        "by_provider": by_provider,
    }
