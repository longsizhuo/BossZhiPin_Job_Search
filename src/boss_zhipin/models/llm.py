"""LLM 招呼语生成的统一封装（OpenAI 兼容端点）。

设计要点：
- 不再分 provider：统一一个 **OpenAI 兼容端点** = ``LLM_BASE_URL`` +
  ``LLM_API_KEY`` + ``LLM_MODEL``，都用 ``openai`` SDK 访问。DeepSeek /
  Anthropic（``/v1/``）/ OpenAI / 本地 Ollama / 各种中转都是这一条路；切端点
  只是换这三个环境变量（GUI 里选预设会自动填 base_url + model）。
- ``generate_letter`` 是 RAG 流程的主入口：先在 chroma 里召回 ``k=4`` 个简历切片，
  拼进 prompt，再调 LLM 生成招呼语。
- 包了一层 retry（指数退避）+ telemetry（成本/时长/token 落盘）。两者都从环境
  变量读默认值，测试时可以拨小到 0.01s。
"""
from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

from boss_zhipin.audit.telemetry import record_llm_call
from boss_zhipin.models.prompts import assistant_instructions
from boss_zhipin.utils.retry import retry_with_backoff
from boss_zhipin.vectorization import VectorStore, embed_resume

load_dotenv()
log = logging.getLogger(__name__)

def _build_client() -> tuple[OpenAI, str]:
    """从 ``LLM_*`` 环境变量构造 OpenAI 客户端 + model 名。

    - ``LLM_API_KEY``：必填，缺了抛 ``RuntimeError``（提示去 GUI 配）。
    - ``LLM_BASE_URL``：空 → 用 OpenAI 默认端点（SDK 内部回退 api.openai.com）。
    - ``LLM_MODEL``：必填，缺了抛 ``RuntimeError``（不知道端点就没法替你猜 model）。

    全部 call-time 读 ``os.getenv``：GUI 配置页存完即时生效，不用重启。
    """
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "LLM_API_KEY 没设置 —— 在 GUI 配置页选个服务商并填 key，"
            "或在 .env 设 LLM_API_KEY"
        )
    model = os.getenv("LLM_MODEL", "").strip()
    if not model:
        raise RuntimeError(
            "LLM_MODEL 没设置 —— 在 GUI 选个预设会自动填，"
            "或在 .env 设 LLM_MODEL（如 deepseek-chat / gpt-4o / claude-sonnet-4-6）"
        )
    base_url = os.getenv("LLM_BASE_URL", "").strip() or None
    kwargs: dict[str, str] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs), model


def _provider_label(base_url: str | None) -> str:
    """给 telemetry 分组用的短标签——从 base_url 主机名粗略推断。

    只影响 ``logs/llm_calls.jsonl`` 的 ``by_provider`` 分组展示；成本估算按
    ``model`` 名算，跟这个无关。认不出就 ``custom``。
    """
    host = (base_url or "api.openai.com").lower()
    if "deepseek" in host:
        return "deepseek"
    if "anthropic" in host:
        return "claude"
    if "openai" in host:
        return "openai"
    return "custom"


def current_provider_label() -> str:
    """从当前 ``LLM_BASE_URL`` 推 telemetry 短标签——三处 telemetry 调用的统一入口。

    收敛掉散落在 llm / job_matcher / write_response 里的同一段
    ``_provider_label(os.getenv("LLM_BASE_URL", "").strip() or None)`` copy-paste，
    避免某一处漏改导致 ``by_provider`` 分组对不上（曾经就这么错过一次）。
    """
    return _provider_label(os.getenv("LLM_BASE_URL", "").strip() or None)


# 把真正调远端的那一步拆出来，方便单测时整体替换或局部 mock
@retry_with_backoff()
def _call_chat_completion(client: OpenAI, **kwargs):
    """对 ``client.chat.completions.create`` 包一层指数退避重试。"""
    return client.chat.completions.create(**kwargs)


def generate_letter(
    usr_name: str,
    vectorstore: VectorStore,
    job_description: str,
) -> str:
    """RAG 招呼语生成的主入口。

    用哪个端点 / model 由 ``LLM_*`` 环境变量决定（见 ``_build_client``），
    调用方不用再传 provider 名。

    每次调用都会：
    1. 在 chroma 里召回与 JD 最相关的 4 段简历内容；
    2. 拼成 system + user prompt；
    3. 调 LLM（带指数退避重试）；
    4. 把 token 用量 / 延迟 / 估算成本 写一行到 ``logs/llm_calls.jsonl``。

    失败时 telemetry 也会记一行 ``ok=False, error=str(e)``，然后异常向上抛。
    """
    client, llm_model = _build_client()
    provider_label = current_provider_label()

    relevant_chunks = vectorstore.search(job_description, k=4)
    resume_context = "\n\n".join(relevant_chunks)

    system_prompt = assistant_instructions(usr_name)
    user_prompt = (
        f"工作描述:\n{job_description}\n\n"
        f"简历内容:\n{resume_context}\n\n"
        "要求:\n根据工作描述，寻找出简历里最合适的技能都有哪些?求职者的优势是什么?"
    )

    t0 = time.monotonic()
    try:
        response = _call_chat_completion(
            client,
            model=llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=512,
        )
    except Exception as e:
        record_llm_call(
            provider=provider_label, model=llm_model,
            input_tokens=0, output_tokens=0,
            latency_ms=int((time.monotonic() - t0) * 1000),
            ok=False, error=f"{type(e).__name__}: {e}",
        )
        raise

    letter = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    record_llm_call(
        provider=provider_label,
        model=llm_model,
        input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
        output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        latency_ms=int((time.monotonic() - t0) * 1000),
        letter_len=len(letter),
        ok=True,
    )
    return letter


if __name__ == "__main__":
    from boss_zhipin.models.job_matcher import extract_resume_text
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    usr_name = "龙思卓"
    resume_path = "../resume/my_cover.pdf"
    import os
    if os.path.exists(resume_path):
        resume_text = extract_resume_text(resume_path)
        vectorstore = embed_resume(resume_text, "./vectorstores")
        job_description = """岗位职责：
1、负责AI对话工作流的设计与搭建，包括但不限于客服、销售等场景 。
2、进行提示词工程开发与优化，构建高质量的AI交互体验 。

任职要求：
1、本科及以上学历，计算机相关专业优先 。
2、熟练使用Coze/Dify/FastGPT等AI工作流搭建工具。
"""
        print(generate_letter(usr_name, vectorstore, job_description))
    else:
        print(f"Skipping test, resume file not found: {resume_path}")
