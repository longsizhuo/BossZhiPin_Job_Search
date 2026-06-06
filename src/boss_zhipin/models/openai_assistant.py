"""OpenAI Assistants 模式：上传简历到 Vector Store + 建/复用 Assistant。

Assistants API 跟 chat.completions API 不一样：
- 一个 Assistant 对应一个被绑定了 vector store 的对话角色，可以复用。
- 我们把 ``assistant.id`` 缓存到 ``./assistant.json``，下次跑直接复用。
  这个文件在 ``.gitignore`` 里，不会被意外提交。
- vector store 没缓存 —— 每次新建 assistant 时简历会被重新上传。如果你换
  简历后想重新生成 assistant，删掉 ``assistant.json`` 即可。
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from boss_zhipin.models.prompts import assistant_instructions

load_dotenv()
log = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")

DEFAULT_RESUME_PATH = "resume/my_cover.pdf"
ASSISTANT_FILE_PATH = "assistant.json"


def create_assistant(
    usr_name: str,
    chatgpt_model: str,
    client,
    resume_path: str | None = None,
) -> str:
    """新建或加载一个绑定简历的 OpenAI Assistant。

    Args:
        usr_name: 用户名，会注入 ``assistant_instructions`` prompt 的签名。
        chatgpt_model: model 名（如 ``"gpt-4o"``）。
        client: 已构造好的 ``openai.OpenAI`` 客户端实例。
        resume_path: 简历 PDF 路径。None 时用 ``DEFAULT_RESUME_PATH``。

    Returns:
        assistant_id 字符串。
    """
    resume_path = resume_path or DEFAULT_RESUME_PATH

    if os.path.exists(ASSISTANT_FILE_PATH):
        with open(ASSISTANT_FILE_PATH, "r") as file:
            assistant_data = json.load(file)
            log.info("从 %s 加载到已有 assistant id", ASSISTANT_FILE_PATH)
            return assistant_data["assistant_id"]

    if not Path(resume_path).is_file():
        raise FileNotFoundError(
            f"简历文件不存在：{resume_path}。把 PDF 放到这个路径，"
            f"或者在 .env 里设 RESUME_PATH 指向其他位置。"
        )

    vector_store = client.vector_stores.create(name="My Resume")
    log.info("已建 OpenAI vector store: %s", vector_store.id)

    with open(resume_path, "rb") as resume_file:
        client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id, files=[resume_file]
        )

    assistant = client.beta.assistants.create(
        instructions=assistant_instructions(usr_name),
        model=chatgpt_model,
        tools=[{"type": "file_search"}],
    )
    assistant = client.beta.assistants.update(
        assistant_id=assistant.id,
        tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
    )

    with open(ASSISTANT_FILE_PATH, "w") as file:
        json.dump({"assistant_id": assistant.id}, file)
        log.info("新建 assistant 完成，id 已写到 %s", ASSISTANT_FILE_PATH)

    return assistant.id
