import json
import re
import time

from audit import log_attempt, validate_letter
from models.llm import PROVIDERS, generate_letter
from website_oper import finding_jobs


def create_thread(client):
    # Function to create a new thread and return its ID
    try:
        response = client.beta.threads.create()  # No assistant_id needed
        thread_id = response.id
        return thread_id
    except Exception as e:
        print(f"Error creating thread: {e}")
        return None


def chat(user_input, assistant_id, client, usr_name: str = "", thread_id=None):
    if thread_id is None:
        thread_id = create_thread(client)
        if thread_id is None:
            return json.dumps({"error": "Failed to create a new thread"})

    print(f"Received message: {user_input} in thread {thread_id}")

    try:
        client.beta.threads.messages.create(
            thread_id=thread_id, role="user", content=user_input
        )
        run = client.beta.threads.runs.create(
            thread_id=thread_id, assistant_id=assistant_id
        )

        # 等 run 完成。原来这里在 queued / in_progress 时直接 busy-loop 不 sleep，
        # 单次招呼可以打几万次 API；同时 failed / cancelled / expired 没处理，
        # 命中就是死循环。加上 5 分钟硬超时 + 每轮 1s sleep + 终态识别。
        TERMINAL_FAIL_STATES = {"failed", "cancelled", "expired", "incomplete"}
        deadline = time.time() + 300
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id, run_id=run.id, timeout=60
            )
            if run_status.status == "completed":
                break
            if run_status.status in TERMINAL_FAIL_STATES:
                err = f"OpenAI run 进入失败终态：{run_status.status}"
                print(f"[chat] {err}")
                return json.dumps({"error": err})
            if time.time() > deadline:
                print("[chat] run 等待超过 5 分钟，放弃")
                return json.dumps({"error": "run timeout (>300s)"})
            time.sleep(1)

        messages = client.beta.threads.messages.list(thread_id=thread_id)
        assistant_message = messages.data[0].content[0].text.value

        formatted_message = assistant_message.replace("\n", " ").replace(" ", "")
        if usr_name:
            formatted_message = formatted_message.replace(f"真诚的，{usr_name}", "")
        formatted_message = re.sub(r"【.*?】", "", formatted_message)
        return formatted_message

    except Exception as e:
        print(f"An error occurred: {e}")
        return json.dumps({"error": str(e)})


def send_response_and_go_back(response):
    finding_jobs.send_chat_message(response)
    time.sleep(10)
    finding_jobs.navigate_back()


def _resolve_model_name(models: str, assistant_id: str | None) -> str:
    if models in PROVIDERS:
        return PROVIDERS[models]["default_model"] or ""
    if models == "chatgpt":
        return f"assistant:{assistant_id}" if assistant_id else "assistant"
    return models


def send_job_descriptions_to_chat(
    usr_name,
    url,
    browser_type,
    label,
    models: str,
    client_openAI=None,
    assistant_id=None,
    vectorstore=None,
    dry_run: bool = False,
):
    # 开始浏览并获取工作描述
    finding_jobs.open_browser_with_options(url, browser_type)
    finding_jobs.log_in()

    job_index = 1
    iteration = 0
    # 第一轮按 label（如果有的话）筛 tag；后续轮次留在当前 feed，无需重复点
    finding_jobs.select_dropdown_option(label)
    while True:
        try:
            iteration += 1
            print(f"\n=== 第 {iteration} 轮: 处理 job_index={job_index} ===")
            job_description = finding_jobs.get_job_description_by_index(job_index)
            if job_description:
                element = finding_jobs.get_text_by_css(".op-btn.op-btn-chat")
                print(f"chat 按钮文字: {element!r}")
                if element == "立即沟通":
                    if models in ("deepseek", "claude"):
                        response = generate_letter(usr_name, vectorstore, job_description, model=models)
                    else:
                        response = chat(
                            user_input=job_description,
                            client=client_openAI,
                            assistant_id=assistant_id,
                            usr_name=usr_name,
                        )

                    validation = validate_letter(response)
                    resolved_model = _resolve_model_name(models, assistant_id)

                    if not validation.ok:
                        print(f"[BLOCKED] {validation.reasons} — preview: {response[:80]!r}")
                        log_attempt(
                            provider=models,
                            model=resolved_model,
                            job_description=job_description,
                            letter=response,
                            validation=validation,
                            dry_run=dry_run,
                            sent=False,
                        )
                    elif dry_run:
                        print(f"[DRY-RUN] Generated letter ({len(response)} chars). Not sending.")
                        print(f"--- letter ---\n{response}\n--------------")
                        log_attempt(
                            provider=models,
                            model=resolved_model,
                            job_description=job_description,
                            letter=response,
                            validation=validation,
                            dry_run=True,
                            sent=False,
                        )
                    else:
                        print(response)
                        time.sleep(1)
                        contact_xpath = "//*[@id='wrap']/div[2]/div[2]/div/div/div[2]/div/div[1]/div[2]/a[2]"
                        finding_jobs.click_by_xpath(contact_xpath, timeout=10)
                        finding_jobs.wait_for_css("#chat-input", timeout=50)
                        send_response_and_go_back(response)
                        log_attempt(
                            provider=models,
                            model=resolved_model,
                            job_description=job_description,
                            letter=response,
                            validation=validation,
                            dry_run=False,
                            sent=True,
                        )

            time.sleep(3)
            job_index += 1

        except Exception as e:
            print(f"An error occurred: {e}")
            break