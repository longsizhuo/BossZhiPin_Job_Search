"""单个岗位的主循环：抓 JD → 生成招呼语 → 校验 → 发送（或 dry-run）。

调用图：

.. code-block:: text

    main.py
      └─ send_job_descriptions_to_chat
           ├─ finding_jobs.open_browser_with_options / log_in
           ├─ finding_jobs.select_dropdown_option (一次)
           └─ while True:
                ├─ finding_jobs.get_job_description_by_index
                ├─ generate_letter (RAG + OpenAI 兼容端点)
                ├─ validate_letter / log_attempt
                └─ finding_jobs.{click_by_xpath,wait_for_css,send_chat_message,navigate_back}

终止条件：
- 连续 ``MAX_CONSECUTIVE_MISSES`` 次拿不到 JD（推测到列表底部）
- 任何 exception 命中外层 try
"""
from __future__ import annotations

import asyncio
import logging
import os

from boss_zhipin.audit import log_attempt, validate_letter
from boss_zhipin.gui.events import emit as _emit_progress
from boss_zhipin.models.job_matcher import should_apply
from boss_zhipin.models.llm import current_provider_label, generate_letter
from boss_zhipin.website_oper import finding_jobs

log = logging.getLogger(__name__)


async def send_response_and_go_back(response: str) -> None:
    """在 BOSS 沟通页发送 ``response`` 然后退回到列表。"""
    await finding_jobs.send_chat_message(response)
    await asyncio.sleep(10)
    await finding_jobs.navigate_back()


async def send_job_descriptions_to_chat(
    usr_name: str,
    url: str,
    browser_type: str,
    label: str,
    vectorstore=None,
    dry_run: bool = False,
    resume_keywords: list[str] | None = None,
    resume_text: str | None = None,
    min_keyword_match: int = 2,
    min_llm_score: int = 70,
    exclude_keywords: list[str] | None = None,
) -> None:
    """主循环（async）。

    用哪个 LLM 端点 / model 由 ``LLM_*`` 环境变量决定（见 ``llm._build_client``），
    不再按 provider 分支。``label`` 为空字符串时跳过下拉筛选，沿用 BOSS 默认推荐 feed。

    ``dry_run=True`` 时不点"立即沟通"，但 LLM 仍会调、招呼语仍会校验和写日志，
    用来调 prompt。

    整段必须包在 ``uc.loop().run_until_complete(...)`` 里一次性跑完，
    不能拆成多个 ``run_until_complete`` —— nodriver CDP 在事件循环停顿期间
    会进入半死状态，下次 evaluate 直接 hang。详见模块 docstring。
    """
    # audit log（letters.jsonl）那一列的 provider/model 标签——从当前 LLM_* 推。
    # 真实运行时 token / 成本由 generate_letter 里的 telemetry 单独记。
    llm_model = os.getenv("LLM_MODEL", "").strip()
    provider_label = current_provider_label()

    await finding_jobs.open_browser_with_options(url, browser_type)
    _emit_progress("browser_started")
    await finding_jobs.log_in()
    _emit_progress("login_ok")

    job_index = 1
    iteration = 0
    consecutive_misses = 0
    # 一旦 LLM 评分走了 fail-open（缺配置 / 调用挂 / 解析不出分），第二层过滤其实在
    # 全放行。只在本轮**首次**遇到时提示一次，别每个岗位刷屏。
    degraded_warned = False
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
                _emit_progress("job_found", index=job_index, jd_preview=job_description[:80])
                element = await finding_jobs.get_text_by_css(".op-btn.op-btn-chat")
                log.info("chat 按钮文字: %r", element)
                if element == "立即沟通":
                    # ====== 多层过滤：黑名单 + 关键词 + 向量 + LLM ======
                    if resume_text:
                        apply, details = await asyncio.to_thread(
                            should_apply,
                            job_description, resume_keywords, resume_text,
                            min_keyword_match, min_llm_score, exclude_keywords, vectorstore
                        )
                        # 评分降级（fail-open）首次出现时显式告警一次——否则用户只看到
                        # 一堆岗位"通过"，不知道第二层 LLM 过滤其实没在跑。
                        if details.get("scoring_degraded") and not degraded_warned:
                            degraded_warned = True
                            log.warning(
                                "⚠️ LLM 评分暂时不可用（%s），本轮所有岗位按放行处理",
                                details.get("reason", ""),
                            )
                            _emit_progress("scoring_degraded", detail=details.get("reason", ""))
                        if not apply:
                            stage = details.get("stage", "unknown")
                            if stage == "blacklist":
                                log.info(
                                    "⏭️ [跳过 #%d] 触发黑名单: %s",
                                    job_index, details["reason"],
                                )
                            elif stage == "keyword":
                                log.info(
                                    "⏭️ [跳过 #%d] 关键词匹配不足: 命中 %s - %s",
                                    job_index, details["matched_keywords"], details["reason"],
                                )
                            elif stage == "vector_search":
                                log.info(
                                    "⏭️ [跳过 #%d] 语义不匹配: %s",
                                    job_index, details["reason"],
                                )
                            else:
                                log.info(
                                    "⏭️ [跳过 #%d] LLM 评分 %s/%s: %s",
                                    job_index, details.get("score"), details.get("threshold"), details.get("reason"),
                                )
                            _emit_progress(
                                "job_skipped",
                                index=job_index,
                                reason=stage,
                                detail=details.get("reason", ""),
                                score=details.get("score"),
                                threshold=details.get("threshold"),
                                matched=details.get("matched_keywords"),
                            )
                            job_index += 1
                            await asyncio.sleep(3)
                            continue
                        log.info("✅ [匹配 #%d] 关键词命中: %s", job_index, details["matched_keywords"])
                        if "score" in details:
                            log.info("   LLM 评分: %s/100 - %s", details["score"], details["reason"])
                    # ====== 过滤结束 ======

                    # LLM 评分（resume_text 为空时没跑过滤 → None），带进 letter_sent 事件，
                    # 让 GUI 进度面板能看到"这条招呼语对应的岗位匹配多少分"。
                    match_score = details.get("score") if resume_text else None

                    # LLM 调用是同步阻塞的 HTTP 请求，扔到 thread pool 跑
                    # 避免阻塞事件循环 → 卡死 nodriver CDP heartbeat
                    response = await asyncio.to_thread(
                        generate_letter,
                        usr_name, vectorstore, job_description,
                    )

                    validation = validate_letter(response)

                    if not validation.ok:
                        log.warning(
                            "[BLOCKED] %s — preview: %r",
                            validation.reasons, response[:80],
                        )
                        log_attempt(
                            provider=provider_label, model=llm_model,
                            job_description=job_description, letter=response,
                            validation=validation, dry_run=dry_run, sent=False,
                        )
                        _emit_progress("letter_sent", index=job_index, status="blocked",
                                       score=match_score, letter_len=len(response))
                    elif dry_run:
                        log.info(
                            "[DRY-RUN] 招呼语 (%d 字符) 不发送。--- letter ---\n%s\n--------------",
                            len(response), response,
                        )
                        log_attempt(
                            provider=provider_label, model=llm_model,
                            job_description=job_description, letter=response,
                            validation=validation, dry_run=True, sent=False,
                        )
                        _emit_progress("letter_sent", index=job_index, status="dry_run",
                                       score=match_score, letter_len=len(response))
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
                            provider=provider_label, model=llm_model,
                            job_description=job_description, letter=response,
                            validation=validation, dry_run=False, sent=True,
                        )
                        _emit_progress("letter_sent", index=job_index, status="sent",
                                       score=match_score, letter_len=len(response))
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
                    _emit_progress("feed_exhausted", total=job_index - 1)
                    break

            await asyncio.sleep(3)
            job_index += 1

        except Exception as e:
            log.exception("主循环抛异常: %s", e)
            _emit_progress(
                "error",
                stage=f"job_index={job_index}",
                message=f"{type(e).__name__}: {e}",
            )
            break
