"""三家 LLM provider 的统一封装。

设计要点：
- 三家（DeepSeek / OpenAI / Claude）都用 ``openai`` SDK 通过 ``base_url`` 改写
  来访问。Claude 走 Anthropic 官方的 OpenAI 兼容端点 ``/v1/``。
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

PROVIDERS: dict[str, dict[str, str | None]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
    },
    "claude": {
        "base_url": "https://api.anthropic.com/v1/",
        "api_key_env": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-6",
    },
    "openai": {
        "base_url": None,
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
    },
}


def _build_client(provider: str) -> tuple[OpenAI, str]:
    """根据 provider 名构造 OpenAI 客户端 + 默认 model 名。

    Raises:
        ValueError: 未知 provider。
        RuntimeError: 环境变量里没找到对应 API key。
    """
    if provider not in PROVIDERS:
        raise ValueError(
            f"Unsupported provider: {provider!r}. Choose from {list(PROVIDERS)}."
        )
    cfg = PROVIDERS[provider]
    api_key = os.getenv(cfg["api_key_env"])
    if not api_key:
        raise RuntimeError(f"Environment variable {cfg['api_key_env']} is not set")
    kwargs: dict[str, str] = {"api_key": api_key}
    if cfg["base_url"]:
        kwargs["base_url"] = cfg["base_url"]
    return OpenAI(**kwargs), cfg["default_model"]


# 把真正调远端的那一步拆出来，方便单测时整体替换或局部 mock
@retry_with_backoff()
def _call_chat_completion(client: OpenAI, **kwargs):
    """对 ``client.chat.completions.create`` 包一层指数退避重试。"""
    return client.chat.completions.create(**kwargs)


def generate_letter(
    usr_name: str,
    vectorstore: VectorStore,
    job_description: str,
    model: str = "deepseek",
) -> str:
    """RAG 招呼语生成的主入口。

    ``model`` 是 provider 名（"deepseek" / "claude" / "openai"），实际用的
    LLM 是该 provider 的 ``default_model``。

    每次调用都会：
    1. 在 chroma 里召回与 JD 最相关的 4 段简历内容；
    2. 拼成 system + user prompt；
    3. 调 LLM（带指数退避重试）；
    4. 把 token 用量 / 延迟 / 估算成本 写一行到 ``logs/llm_calls.jsonl``。

    失败时 telemetry 也会记一行 ``ok=False, error=str(e)``，然后异常向上抛。
    """
    client, llm_model = _build_client(model)

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
            provider=model, model=llm_model,
            input_tokens=0, output_tokens=0,
            latency_ms=int((time.monotonic() - t0) * 1000),
            ok=False, error=f"{type(e).__name__}: {e}",
        )
        raise

    letter = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    record_llm_call(
        provider=model,
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
        print(generate_letter(usr_name, vectorstore, job_description, model="deepseek"))
    else:
        print(f"Skipping test, resume file not found: {resume_path}")
