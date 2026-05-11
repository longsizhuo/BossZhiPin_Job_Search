import json
import time
from models.llm import PROVIDERS, generate_letter

from audit import log_attempt, validate_letter
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


def chat(user_input, assistant_id, client, thread_id=None):
    if thread_id is None:
        thread_id = create_thread(client)
        if thread_id is None:
            return json.dumps({"error": "Failed to create a new thread"})

    print(f"Received message: {user_input} in thread {thread_id}")

    # Run the Assistant
    try:
        # Add the user's message to the thread
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_input
        )

        # Start the Assistant Run
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )

        # Check if the Run requires action (function call)
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id,
                timeout=60  # 设置超时时间为60秒
            )

            if run_status.status == 'completed':
                break
            elif run_status.status == 'requires_action':
                # Here you can handle specific actions if your assistant requires them
                # ...
                time.sleep(1)  # Wait for a second before checking again

        # Retrieve and return the latest message from the assistant
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        assistant_message = messages.data[0].content[0].text.value

        # 将换行符替换为一个空格
        formatted_message = assistant_message.replace("\n", " ").replace(" ", "").replace("真诚的，龙思卓", "")
        import re
        formatted_message = re.sub(r'【.*?】', '', formatted_message)


        # response_data = json.dumps({"response": assistant_message, "thread_id": thread_id})
        return formatted_message

    except Exception as e:
        print(f"An error occurred: {e}")
        error_response = json.dumps({"error": str(e)})
        return error_response


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
    while True:
        try:
            iteration += 1
            print(f"\n=== 第 {iteration} 轮: 处理 job_index={job_index} ===")
            finding_jobs.select_dropdown_option(None, label)
            job_description = finding_jobs.get_job_description_by_index(job_index)
            if job_description:
                element = finding_jobs.get_text_by_css(".op-btn.op-btn-chat")
                print(f"chat 按钮文字: {element!r}")
                if element == "立即沟通":
                    if models in ("deepseek", "claude"):
                        response = generate_letter(usr_name, vectorstore, job_description, model=models)
                    else:
                        response = chat(user_input=job_description, client=client_openAI, assistant_id=assistant_id)

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
            # job_index += 1

        except Exception as e:
            print(f"An error occurred: {e}")
            break