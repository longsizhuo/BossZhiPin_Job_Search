import os

from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain_deepseek import ChatDeepSeek
from langchain_core.prompts import PromptTemplate
from models.prompts import assistant_instructions
from vectorization import embed_pdf

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

# 生成求职信
def generate_letter(usr_name, vectorstore, job_description, model="deepseek"):
    prompt = PromptTemplate.from_template(f"""
        {assistant_instructions(usr_name)}
        工作描述:
        {job_description}
        简历内容:
        {{context}}
        要求:
        {{question}}
    """)
    question = "根据工作描述，寻找出简历里最合适的技能都有哪些?求职者的优势是什么?"
    relevant_docs = vectorstore.as_retriever().invoke(job_description)

    if model == "deepseek":
        llm = ChatDeepSeek(
            api_key=DEEPSEEK_API_KEY,
            model="deepseek-chat",
            temperature=0.4,
            max_tokens=512,
            timeout=None,
            max_retries=2,
        )
    else:
        raise ValueError("Unsupported model")
        # llm = ChatOpenAI(temperature=0.3, openai_api_base=OPENAI_BASE_URL, openai_api_key=OPENAI_API_KEY)
    document_chain = create_stuff_documents_chain(llm, prompt)
    response = document_chain.invoke({
        "assistant_instructions": assistant_instructions(usr_name),
        "job_description": job_description,
        "context": relevant_docs,
        "question": question
    })
    letter = response
    #去掉所有换行符，防止分成多段消息
    # letter = letter.replace('\n', ' ')
    # letter = " ".join(letter.split())

    return letter

# Test part
if __name__ == '__main__':
    # 测试生成求职信
    usr_name = "龙思卓"
    vectorstore = embed_pdf("../resume/my_cover.pdf", "./vectorstores")
    job_description = """岗位职责：
1、负责AI对话工作流的设计与搭建，包括但不限于客服、销售等场景 。
2、进行提示词工程开发与优化，构建高质量的AI交互体验 。
3、参与AI+RPA自动化流程开发，提升获客和运营效率 。
4、开发和维护AI内容生产工具，支持文章、视频脚本等内容创作 。
5、构建和优化基于知识库的智能问答系统 。
6、开发AI工具调用脚本，提升自动化程度 。

任职要求：
1、本科及以上学历，计算机相关专业优先 。
2、熟练使用Coze/Dify/FastGPT等AI工作流搭建工具。
3、 具备提示词工程相关经验，能够构建复杂对话流程。
4、 有AI应用开发实践经验，包括但不限于: AI客服、销售系统搭建、内容生产自动化、知识库构建 。
5、具备基本的编程能力，能够开发简单的工具脚本， 对AI技术有浓厚兴趣，持续关注行业发展 。

加分项：
1、有RAG系统开发经验 。
2、有多模态AI应用开发经验。
来源：BOSS直聘
链接：https://www.zhipin.com/web/geek/job-recommend"""

    model = "deepseek"  # 或者 "chatgpt"

    letter = generate_letter(usr_name, vectorstore, job_description, model)
    print(letter)