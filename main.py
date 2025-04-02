from openai import OpenAI
from packaging import version
import openai

from models.openai_assistant import create_assistant, OPENAI_API_KEY
from vectorization import embed_pdf
from website_oper.write_response import send_job_descriptions_to_chat

if __name__ == '__main__':
    while True:
        model = input("Which model do you want to use? (deepseek: 1, chatgpt: 2, Claud: 3): ")
        if model not in ["1", "2", "3"]:
            print("Invalid model. Please enter either 'deepseek', 'chatgpt', or 'Claud'.")
        else:
            break

    url = "https://www.zhipin.com/web/geek/job-recommend?ka=header-job-recommend"
    browser_type = "chrome"
    label = "后端开发（成都）"  # 想要选择的下拉菜单项

    if model == "1":
        # DeepSeek
        vectorstore = embed_pdf("./resume/my_cover.pdf", "./vectorstores")
        send_job_descriptions_to_chat(url, browser_type, label, "deepseek", vectorstore=vectorstore)

    elif model == "2":
        chatgpt_model = {1: "gpt-4o", 2: "gpt-4o-turbo"}[int(input("Which ChatGPT model do you want to use? (gpt-4o: 1, gpt-4o-turbo: 2): "))]
        # Check version compatibility
        required_version = version.parse("1.1.1")
        current_version = version.parse(openai.__version__)
        # Check OpenAI version compatibility
        if current_version < required_version:
            raise ValueError(
                f"Error: OpenAI version {openai.__version__} is less than the required version 1.1.1"
            )
        else:
            print("OpenAI version is compatible.")
        # It will come from frontend
        client_openAI = OpenAI(api_key=OPENAI_API_KEY)
        assistant_id = create_assistant(chatgpt_model ,client_openAI)
        send_job_descriptions_to_chat(url, browser_type, label, "chatgpt", client_openAI=client_openAI, assistant_id=assistant_id)
    elif model == "3":
        # 暂时弃用，以后开发
        pass
