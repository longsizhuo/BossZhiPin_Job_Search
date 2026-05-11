import json
import os
from pathlib import Path

from dotenv import load_dotenv

from models.prompts import assistant_instructions

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")

DEFAULT_RESUME_PATH = "resume/my_cover.pdf"
ASSISTANT_FILE_PATH = "assistant.json"


def create_assistant(usr_name, chatgpt_model, client, resume_path: str | None = None):
    """Create (or load) an OpenAI Assistant backed by the user's PDF resume.

    ``resume_path`` defaults to ``./resume/my_cover.pdf``; pass the path resolved
    from the ``RESUME_PATH`` env var (or wherever) to override it.
    """
    resume_path = resume_path or DEFAULT_RESUME_PATH

    if os.path.exists(ASSISTANT_FILE_PATH):
        with open(ASSISTANT_FILE_PATH, "r") as file:
            assistant_data = json.load(file)
            print(f"Loaded existing assistant ID from {ASSISTANT_FILE_PATH}")
            return assistant_data["assistant_id"]

    if not Path(resume_path).is_file():
        raise FileNotFoundError(
            f"简历文件不存在：{resume_path}。把 PDF 放到这个路径，"
            f"或者在 .env 里设 RESUME_PATH 指向其他位置。"
        )

    vector_store = client.vector_stores.create(name="My Resume")
    print(f"Created OpenAI vector store: {vector_store.id}")

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
        print(f"Created a new assistant, saved ID to {ASSISTANT_FILE_PATH}")

    return assistant.id
