import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from models.openai_assistant import create_assistant, OPENAI_API_KEY
from vectorization import embed_pdf
from website_oper.write_response import send_job_descriptions_to_chat

load_dotenv()

PROVIDER_ENV_KEYS: dict[str, str] = {
    "deepseek": "DEEPSEEK_API_KEY",
    "chatgpt": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}

PROVIDER_SIGNUP: dict[str, str] = {
    "deepseek": "https://platform.deepseek.com/api_keys",
    "chatgpt": "https://platform.openai.com/api-keys",
    "claude": "https://console.anthropic.com/settings/keys",
}


def detect_providers() -> list[str]:
    return [name for name, env in PROVIDER_ENV_KEYS.items() if os.getenv(env)]


def pick_provider() -> str:
    available = detect_providers()
    if not available:
        print("❌ 没在环境里找到任何 LLM provider 的 API key。")
        print("   去这些地方申请一个填进 .env（仓库里有 .env.example 可以参考）：")
        for name, url in PROVIDER_SIGNUP.items():
            print(f"     • {PROVIDER_ENV_KEYS[name]:<22} {url}")
        sys.exit(1)
    if len(available) == 1:
        provider = available[0]
        print(f"✅ 检测到只配了 {PROVIDER_ENV_KEYS[provider]}，自动选用：{provider}")
        return provider
    print(f"检测到 {len(available)} 个 provider 都配了 key，请选一个：")
    for i, name in enumerate(available, 1):
        print(f"  {i}. {name:<10} ({PROVIDER_ENV_KEYS[name]})")
    while True:
        choice = input(f"输入序号 (1-{len(available)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(available):
            return available[int(choice) - 1]
        print("无效输入，再试一次")


def ensure_usr_name() -> str:
    name = os.getenv("BOSS_USR_NAME", "").strip()
    if name:
        return name
    while True:
        name = input("请输入你的名字（用于打招呼语结尾的署名）: ").strip()
        if name:
            return name
        print("不能为空")


def ensure_resume_path() -> str:
    resume_path = os.getenv("RESUME_PATH", "").strip() or "resume/my_cover.pdf"
    if not Path(resume_path).is_file():
        print(f"❌ 找不到简历文件：{resume_path}")
        print(f"   请把 PDF 简历放到这个路径，或者在 .env 设 RESUME_PATH 指向其他位置。")
        sys.exit(1)
    return resume_path


def get_label() -> str:
    """求职 tag 是可选的——为空就让 BOSS 给默认推荐 feed。"""
    return os.getenv("BOSS_LABEL", "").strip()


if __name__ == "__main__":
    dry_run = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")
    if dry_run:
        print("⚠️  DRY_RUN=1 — 招呼语只会生成 + 写日志，不会真的发到 BOSS")

    provider = pick_provider()
    usr_name = ensure_usr_name()
    resume_path = ensure_resume_path()
    label = get_label()
    if label:
        print(f"求职 tag：{label}")
    else:
        print("没设 BOSS_LABEL，用 BOSS 默认推荐 feed")

    url = "https://www.zhipin.com/web/geek/job-recommend?ka=header-job-recommend"
    browser_type = "chrome"

    if provider == "deepseek":
        vectorstore = embed_pdf(resume_path, "./vectorstores")
        send_job_descriptions_to_chat(
            usr_name, url, browser_type, label, "deepseek",
            vectorstore=vectorstore, dry_run=dry_run,
        )
    elif provider == "chatgpt":
        chatgpt_model = os.getenv("CHATGPT_MODEL", "").strip() or "gpt-4o"
        print(f"OpenAI 模型：{chatgpt_model}（可用 CHATGPT_MODEL 环境变量覆盖）")
        openai_base_url = os.getenv("OPENAI_BASE_URL", "").strip()
        if openai_base_url:
            print(f"OpenAI base_url 覆盖：{openai_base_url}")
        client_openAI = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=openai_base_url or None,
        )
        assistant_id = create_assistant(
            usr_name, chatgpt_model, client_openAI, resume_path=resume_path
        )
        send_job_descriptions_to_chat(
            usr_name, url, browser_type, label, "chatgpt",
            client_openAI=client_openAI, assistant_id=assistant_id, dry_run=dry_run,
        )
    elif provider == "claude":
        vectorstore = embed_pdf(resume_path, "./vectorstores")
        send_job_descriptions_to_chat(
            usr_name, url, browser_type, label, "claude",
            vectorstore=vectorstore, dry_run=dry_run,
        )
