import json
import os
import time
from selenium.webdriver.support import expected_conditions as EC

import openai
from openai import OpenAI
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

import functions
import finding_jobs

# Check OpenAI version compatibility
from packaging import version
from dotenv import load_dotenv

load_dotenv()

required_version = version.parse("1.1.1")
current_version = version.parse(openai.__version__)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if current_version < required_version:
    raise ValueError(
        f"Error: OpenAI version {openai.__version__} is less than the required version 1.1.1"
    )
else:
    print("OpenAI version is compatible.")

class OpenAIClientManager:
    _instance = None
    _client = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self, api_key, base_url=None):
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def get_client(self):
        if self._client is None:
            raise ValueError("OpenAI client not initialized. Please set API key first.")
        return self._client

# 全局单例
openai_manager = OpenAIClientManager.get_instance()


def create_thread(client):
    # Function to create a new thread and return its ID
    try:
        response = client.beta.threads.create()  # No assistant_id needed
        thread_id = response.id
        return thread_id
    except Exception as e:
        print(f"Error creating thread: {e}")
        return None


def chat(user_input, assistant_id, thread_id=None):
    if thread_id is None:
        thread_id = create_thread(openai_manager.get_client())
        if thread_id is None:
            return json.dumps({"error": "Failed to create a new thread"})

    print(f"Received message: {user_input} in thread {thread_id}")

    # Run the Assistant
    try:
        # Add the user's message to the thread
        openai_manager.get_client().beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_input
        )

        # Start the Assistant Run
        run = openai_manager.get_client().beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )

        # Check if the Run requires action (function call)
        while True:
            run_status = openai_manager.get_client().beta.threads.runs.retrieve(
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
        messages = openai_manager.get_client().beta.threads.messages.list(thread_id=thread_id)
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


def send_response_to_chat_box(driver, response):
    # 定位聊天输入框
    chat_box = driver.find_element(By.XPATH, "//*[@id='chat-input']")

    # 清除输入框中可能存在的任何文本
    chat_box.clear()

    # 将响应粘贴到输入框
    chat_box.send_keys(response)
    time.sleep(3)

    # 模拟按下回车键来发送消息
    chat_box.send_keys(Keys.ENTER)
    time.sleep(1)


def send_response_and_go_back(driver, response):
    # 调用函数发送响应
    send_response_to_chat_box(driver, response)

    time.sleep(10)
    # 返回到上一个页面
    driver.back()
    time.sleep(3)


def send_job_descriptions_to_chat(url, browser_type, label):
    # 这个函数会在用户点击"开始任务"后被调用
    client = openai_manager.get_client()  # 获取已初始化的客户端
    # 开始浏览并获取工作描述
    finding_jobs.open_browser_with_options(url, browser_type)
    finding_jobs.log_in()

    job_index = 1  # 开始的索引
    while True:
        try:
            # 获取 driver 实例
            driver = finding_jobs.get_driver()

            # 更改下拉列表选项
            finding_jobs.select_dropdown_option(driver, label)
            # 调用 finding_jobs.py 中的函数来获取描述
            job_description = finding_jobs.get_job_description_by_index(job_index)
            if job_description:
                element = driver.find_element(By.CSS_SELECTOR, '.op-btn.op-btn-chat').text
                print(element)
                if element == '立即沟通':
                    # 发送描述到聊天并打印响应
                    response = chat(job_description, assistant_id)
                    print(response)
                    time.sleep(1)
                    # 点击沟通按钮

                    contact_button = driver.find_element(By.XPATH,
                                                         "//*[@id='wrap']/div[2]/div[2]/div/div/div[2]/div/div[1]/div[2]/a[2]")

                    contact_button.click()

                    # 等待回复框出现
                    xpath_locator_chat_box = "//*[@id='chat-input']"
                    chat_box = WebDriverWait(driver, 50).until(
                        EC.presence_of_element_located((By.XPATH, xpath_locator_chat_box))
                    )

                    # 调用函数发送响应
                    send_response_and_go_back(driver, response)

            # 等待一定时间后处理下一个工作描述
            time.sleep(3)
            # job_index += 1

        except Exception as e:
            print(f"An error occurred: {e}")
            break


if __name__ == '__main__':
    url = "https://www.zhipin.com/web/geek/job-recommend?ka=header-job-recommend"
    browser_type = "chrome"
    label = "iOS（深圳）"  # 想要选择的下拉菜单项
    assistant_id = functions.create_assistant(openai_manager.get_client())
    send_job_descriptions_to_chat(url, browser_type, label, assistant_id=assistant_id)
