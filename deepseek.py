from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import SystemMessage, HumanMessage
from selenium.webdriver.common.by import By
import finding_jobs
from dotenv import load_dotenv
import time
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import Keys
import os

load_dotenv()
if not os.getenv("DEEPSEEK_API_KEY"):
    raise RuntimeError("No key provided")


def generate_vector_store(file_path):
    loader = PyPDFLoader(file_path)

    docs = loader.load()

    print(len(docs))

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200, add_start_index=True
    )
    all_splits = text_splitter.split_documents(docs)
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-mpnet-base-v2"
    )

    len(all_splits)
    vector_store = InMemoryVectorStore(embeddings)
    ids = vector_store.add_documents(documents=all_splits)
    print(ids)

    return vector_store


def generate_by_ds(vector_store, job_description):
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 1},
    )
    question = "结合该简历中求职者的工作经历(experience)、项目经历(projects)以及技能(skills)帮我生成一份求职招聘"

    system_prompt = """
        首先查看一下下面的工作描述，然后结合简历内容判断一下该候选人是否匹配这个职位，
        如果是匹配的，那么来直接给HR写一个礼貌专业的求职消息, 且仅使用三句话，字数严格限制在300以内。要求能够用专业的语言结合简历中的经历和技能,并结合应聘工作的描述,来阐述自己的优势,尽最大可能打动招聘者。始终使用中文来进行消息的编写。开头是招聘负责人, 结尾附上求职者联系方式。这是一份求职消息，不要包含求职内容以外的东西,例如“根据您上传的求职要求和个人简历,我来帮您起草一封求职邮件：”这一类的内容，以便于我直接自动化复制粘贴发送。
        如果你发现不太匹配，那么仅回答“不匹配”三个字，不要有额外的内容显示。
        工作描述
        {job_description}
        简历内容:
        {context}
    """
    docs = retriever.invoke(question)
    context = "".join(d.page_content for d in docs)
    system_prompt_fmt = system_prompt.format(
        context=context, job_description=job_description
    )

    llm = ChatDeepSeek(
        model="deepseek-chat",
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        # other params...
    )
    response = llm.invoke(
        [SystemMessage(content=system_prompt_fmt), HumanMessage(content=question)]
    )
    content = response.content
    if content == "不匹配":
        raise RuntimeError("Mismatched position, abort")
    return content


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


def send_job_descriptions_to_chat(url, browser_type, label, vector_store=None):
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
                element = driver.find_element(
                    By.CSS_SELECTOR, ".op-btn.op-btn-chat"
                ).text
                print(element)
                if element == "立即沟通":
                    response = generate_by_ds(vector_store, job_description)
                    # # 发送描述到聊天并打印响应
                    # if should_use_langchain():
                    #     response = generate_letter(vectorstore, job_description)
                    # else:
                    #     response = chat(job_description, assistant_id)
                    print(response)
                    time.sleep(1)
                    # 点击沟通按钮

                    contact_button = driver.find_element(
                        By.XPATH,
                        "//*[@id='wrap']/div[2]/div[2]/div/div/div[2]/div/div[1]/div[2]/a[2]",
                    )

                    contact_button.click()

                    # 等待回复框出现
                    xpath_locator_chat_box = "//*[@id='chat-input']"
                    chat_box = WebDriverWait(driver, 50).until(
                        EC.presence_of_element_located(
                            (By.XPATH, xpath_locator_chat_box)
                        )
                    )

                    # 调用函数发送响应
                    send_response_and_go_back(driver, response)

            # 等待一定时间后处理下一个工作描述
            time.sleep(3)
            # job_index += 1

        except Exception as e:
            print(f"An error occurred: {e}")
            break


if __name__ == "__main__":
    file_path = "./resume/my_cover.pdf"
    vector_store = generate_vector_store(file_path)

    url = "https://www.zhipin.com/web/geek/job-recommend?ka=header-job-recommend"
    browser_type = "chrome"
    label = "Python（深圳）"  # 想要选择的下拉菜单项
    send_job_descriptions_to_chat(url, browser_type, label, vector_store)
