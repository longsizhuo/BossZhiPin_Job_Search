import os

from dotenv import load_dotenv
from openai import OpenAI

from models.prompts import assistant_instructions
from vectorization import VectorStore, embed_pdf

load_dotenv()

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


def generate_letter(
    usr_name: str,
    vectorstore: VectorStore,
    job_description: str,
    model: str = "deepseek",
) -> str:
    """Generate a cover-letter style reply using retrieval-augmented context.

    `model` selects the provider; the actual LLM is the provider's default.
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

    response = client.chat.completions.create(
        model=llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=512,
    )
    return response.choices[0].message.content or ""


if __name__ == "__main__":
    usr_name = "龙思卓"
    vectorstore = embed_pdf("../resume/my_cover.pdf", "./vectorstores")
    job_description = """岗位职责：
1、负责AI对话工作流的设计与搭建，包括但不限于客服、销售等场景 。
2、进行提示词工程开发与优化，构建高质量的AI交互体验 。

任职要求：
1、本科及以上学历，计算机相关专业优先 。
2、熟练使用Coze/Dify/FastGPT等AI工作流搭建工具。
"""
    print(generate_letter(usr_name, vectorstore, job_description, model="deepseek"))
