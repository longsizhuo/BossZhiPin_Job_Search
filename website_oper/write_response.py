"""单个岗位的主循环：抓 JD → 生成招呼语 → 校验 → 发送（或 dry-run）。

调用图：

.. code-block:: text

    main.py
      └─ send_job_descriptions_to_chat
           ├─ finding_jobs.open_browser_with_options / log_in
           ├─ finding_jobs.select_dropdown_option (一次)
           └─ while True:
                ├─ finding_jobs.get_job_description_by_index
                ├─ generate_letter (DeepSeek/Claude) 或 chat (OpenAI Assistants)
                ├─ validate_letter / log_attempt
                └─ finding_jobs.{click_by_xpath,wait_for_css,send_chat_message,navigate_back}

终止条件：
- 连续 ``MAX_CONSECUTIVE_MISSES`` 次拿不到 JD（推测到列表底部）
- 任何 exception 命中外层 try
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time

from audit import log_attempt, validate_letter
from audit.telemetry import record_llm_call
from models.job_matcher import should_apply
from models.llm import PROVIDERS, generate_letter
from website_oper import finding_jobs

log = logging.getLogger(__name__)


def create_thread(client):
    """创建一个新的 OpenAI Assistants thread，失败返回 None。"""
    try:
        response = client.beta.threads.create()
        return response.id
    except Exception as e:
        log.error("创建 OpenAI thread 失败: %s", e)
        return None


def chat(user_input, assistant_id, client, usr_name: str = "", thread_id=None):
    """走 OpenAI Assistants API 生成招呼语。

    流程：建/复用 thread → 写一条 user message → create run → 1s 间隔 poll
    run 状态直到 completed（含 failed/cancelled/expired/incomplete 终态识别 +
    5 分钟硬墙）→ 读 assistant 最新回复 → 清掉换行 / 中间空格 / 签名 / 引用标记。

    失败时返回一个 JSON 字符串 ``{"error": "..."}``；上游 ``validate_letter``
    会因为找不到中文字符把它拦掉。
    """
    if thread_id is None:
        thread_id = create_thread(client)
        if thread_id is None:
            return json.dumps({"error": "Failed to create a new thread"})

    log.info("Assistants chat 启动，thread=%s, user_input 长度=%d", thread_id, len(user_input))

    t0 = time.monotonic()
    try:
        client.beta.threads.messages.create(
            thread_id=thread_id, role="user", content=user_input
        )
        run = client.beta.threads.runs.create(
            thread_id=thread_id, assistant_id=assistant_id
        )

        TERMINAL_FAIL_STATES = {"failed", "cancelled", "expired", "incomplete"}
        deadline = time.time() + 300
        last_status = None
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id, run_id=run.id, timeout=60
            )
            last_status = run_status
            if run_status.status == "completed":
                break
            if run_status.status in TERMINAL_FAIL_STATES:
                err = f"OpenAI run 进入失败终态：{run_status.status}"
                log.warning("[chat] %s", err)
                _telemetry_for_run(last_status, t0, ok=False, error=err)
                return json.dumps({"error": err})
            if time.time() > deadline:
                err = "run 等待超过 5 分钟，放弃"
                log.warning("[chat] %s", err)
                _telemetry_for_run(last_status, t0, ok=False, error=err)
                return json.dumps({"error": "run timeout (>300s)"})
            time.sleep(1)

        messages = client.beta.threads.messages.list(thread_id=thread_id)
        assistant_message = messages.data[0].content[0].text.value

        formatted_message = assistant_message.replace("\n", " ").replace(" ", "")
        if usr_name:
            formatted_message = formatted_message.replace(f"真诚的，{usr_name}", "")
        formatted_message = re.sub(r"【.*?】", "", formatted_message)

        _telemetry_for_run(last_status, t0, ok=True, letter_len=len(formatted_message))
        return formatted_message

    except Exception as e:
        log.error("Assistants chat 抛异常: %s", e)
        record_llm_call(
            provider="openai",
            model="assistants-api",
            input_tokens=0, output_tokens=0,
            latency_ms=int((time.monotonic() - t0) * 1000),
            ok=False, error=f"{type(e).__name__}: {e}",
        )
        return json.dumps({"error": str(e)})


def _telemetry_for_run(run_status, t0: float, *, ok: bool, letter_len: int = 0, error: str | None = None) -> None:
    """把 OpenAI run object 里的 usage 字段落到 telemetry。

    Assistants API 在 run 对象上挂 ``usage = { prompt_tokens, completion_tokens,
    total_tokens }``，结构跟 chat completions 不完全一样，单独取一下。
    """
    usage = getattr(run_status, "usage", None) if run_status else None
    model = getattr(run_status, "model", "assistants-api") if run_status else "assistants-api"
    record_llm_call(
        provider="openai",
        model=model or "assistants-api",
        input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
        output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        latency_ms=int((time.monotonic() - t0) * 1000),
        letter_len=letter_len,
        ok=ok,
        error=error,
    )


async def send_response_and_go_back(response: str) -> None:
    """在 BOSS 沟通页发送 ``response`` 然后退回到列表。"""
    await finding_jobs.send_chat_message(response)
    await asyncio.sleep(10)
    await finding_jobs.navigate_back()


def _resolve_model_name(models: str, assistant_id: str | None) -> str:
    """根据 provider 名给 audit log 拼一个 model 标识。

    返回字段分两种语义：

    - **DeepSeek / Claude** → 返回 ``PROVIDERS[provider]["default_model"]``，
      值是真正的模型名（如 ``"deepseek-chat"``）。
    - **OpenAI Assistants** → 返回 ``"assistant:<assistant_id>"``。这里**故意
      不返回模型名**：一个 OpenAI Assistant 资源本身可能在不同时候绑不同
      model（``client.beta.assistants.update``），具体哪次调用用了什么 model
      要看 ``logs/llm_calls.jsonl`` 里 telemetry 行的 ``model`` 字段（那是
      从 run object 上读的真实运行时 model）。

    所以 ``logs/letters.jsonl`` 这一列里 ``model`` 字段对 chatgpt 是 assistant
    资源 id 而不是模型名，这是有意为之 —— 跟 telemetry 配合使用，能 trace
    到具体某次招呼语用的是 assistant 在那一刻绑的哪个 model。
    """
    if models in PROVIDERS:
        return PROVIDERS[models]["default_model"] or ""
    if models == "chatgpt":
        return f"assistant:{assistant_id}" if assistant_id else "assistant"
    return models


async def send_job_descriptions_to_chat(
    usr_name: str,
    url: str,
    browser_type: str,
    label: str,
    models: str,
    client_openAI=None,
    assistant_id=None,
    vectorstore=None,
    dry_run: bool = False,
    resume_keywords: list[str] | None = None,
    resume_text: str | None = None,
    min_keyword_match: int = 2,
    min_llm_score: int = 70,
) -> None:
    """主循环（async）。

    ``models`` 是 provider 名（"deepseek" / "claude" / "chatgpt"），不是具体
    LLM 名。``label`` 为空字符串时跳过下拉筛选，沿用 BOSS 默认推荐 feed。

    ``dry_run=True`` 时不点"立即沟通"，但 LLM 仍会调、招呼语仍会校验和写日志，
    用来调 prompt。

    整段必须包在 ``uc.loop().run_until_complete(...)`` 里一次性跑完，
    不能拆成多个 ``run_until_complete`` —— nodriver CDP 在事件循环停顿期间
    会进入半死状态，下次 evaluate 直接 hang。详见模块 docstring。
    """
    await finding_jobs.open_browser_with_options(url, browser_type)
    await finding_jobs.log_in()

    job_index = 1
    iteration = 0
    consecutive_misses = 0
    # 推荐 feed 末尾、或者某条岗位卡 DOM 没渲染好，都会让 get_job_description
    # 返回 None。连续 N 次拿不到就当列表到底了停掉，否则 job_index 会无限涨。
    MAX_CONSECUTIVE_MISSES = 5
    await finding_jobs.select_dropdown_option(label)
    while True:
        try:
            iteration += 1
            log.info("=== 第 %d 轮: 处理 job_index=%d ===", iteration, job_index)
            job_description = await finding_jobs.get_job_description_by_index(job_index)
            if job_description:
                consecutive_misses = 0
                element = await finding_jobs.get_text_by_css(".op-btn.op-btn-chat")
                log.info("chat 按钮文字: %r", element)
                if element == "立即沟通":
                    # ====== 两层过滤：关键词匹配 + LLM 评分 ======
                    if resume_keywords and resume_text:
                        apply, details = await asyncio.to_thread(
                            should_apply,
                            job_description, resume_keywords, resume_text,
                            min_keyword_match, min_llm_score,
                        )
                        if not apply:
                            stage = details.get("stage", "unknown")
                            if stage == "keyword":
                                log.info(
                                    "⏭️ [跳过 #%d] 关键词匹配不足: 命中 %s - %s",
                                    job_index, details["matched_keywords"], details["reason"],
                                )
                            else:
                                log.info(
                                    "⏭️ [跳过 #%d] LLM 评分 %s/%s: %s",
                                    job_index, details["score"], details["threshold"], details["reason"],
                                )
                            job_index += 1
                            await asyncio.sleep(3)
                            continue
                        log.info("✅ [匹配 #%d] 关键词命中: %s", job_index, details["matched_keywords"])
                        if details.get("score"):
                            log.info("   LLM 评分: %s/100 - %s", details["score"], details["reason"])
                    # ====== 过滤结束 ======

                    # LLM 调用是同步阻塞的 HTTP 请求，扔到 thread pool 跑
                    # 避免阻塞事件循环 → 卡死 nodriver CDP heartbeat
                    if models in ("deepseek", "claude"):
                        response = await asyncio.to_thread(
                            generate_letter,
                            usr_name, vectorstore, job_description, model=models,
                        )
                    else:
                        response = await asyncio.to_thread(
                            chat,
                            user_input=job_description,
                            client=client_openAI,
                            assistant_id=assistant_id,
                            usr_name=usr_name,
                        )

                    validation = validate_letter(response)
                    resolved_model = _resolve_model_name(models, assistant_id)

                    if not validation.ok:
                        log.warning(
                            "[BLOCKED] %s — preview: %r",
                            validation.reasons, response[:80],
                        )
                        log_attempt(
                            provider=models, model=resolved_model,
                            job_description=job_description, letter=response,
                            validation=validation, dry_run=dry_run, sent=False,
                        )
                    elif dry_run:
                        log.info(
                            "[DRY-RUN] 招呼语 (%d 字符) 不发送。--- letter ---\n%s\n--------------",
                            len(response), response,
                        )
                        log_attempt(
                            provider=models, model=resolved_model,
                            job_description=job_description, letter=response,
                            validation=validation, dry_run=True, sent=False,
                        )
                    else:
                        log.info("发送招呼语：%s", response)
                        await asyncio.sleep(1)
                        # 旧版绝对 xpath 在 2026-05 BOSS 改版后失效，
                        # 改成 class 匹配，跟 get_text_by_css(".op-btn.op-btn-chat") 配套。
                        contact_xpath = "//a[contains(@class, 'op-btn-chat')]"
                        await finding_jobs.click_by_xpath(contact_xpath, timeout=10)
                        await finding_jobs.wait_for_css("#chat-input", timeout=50)
                        await send_response_and_go_back(response)
                        log_attempt(
                            provider=models, model=resolved_model,
                            job_description=job_description, letter=response,
                            validation=validation, dry_run=False, sent=True,
                        )
            else:
                consecutive_misses += 1
                log.info(
                    "job_index=%d 拿不到 JD（连续第 %d 次）",
                    job_index, consecutive_misses,
                )
                if consecutive_misses >= MAX_CONSECUTIVE_MISSES:
                    log.info(
                        "连续 %d 个岗位拿不到，推测已到推荐 feed 列表底部，结束",
                        MAX_CONSECUTIVE_MISSES,
                    )
                    break

            await asyncio.sleep(3)
            job_index += 1

        except Exception as e:
            log.exception("主循环抛异常: %s", e)
            break
