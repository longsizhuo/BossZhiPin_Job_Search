import os

from langchain_deepseek import ChatDeepSeek
from langchain.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate

from models.prompts import assistant_instructions

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

# 生成求职信
def generate_letter(vectorstore, job_description, model="deepseek"):
    langchain_prompt_template = f"""
        {assistant_instructions}
        工作描述:
        {job_description}"""+"""
    """

    question = "根据工作描述，寻找出简历里最合适的技能都有哪些?求职者的优势是什么?"

    PROMPT = PromptTemplate.from_template(langchain_prompt_template)
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
        llm = None
        pass
        # llm = ChatOpenAI(temperature=0.3, openai_api_base=OPENAI_BASE_URL, openai_api_key=OPENAI_API_KEY)

    qa_chain = RetrievalQA.from_chain_type(
        llm,
        retriever=vectorstore.as_retriever(),
        # return_source_documents=True,
        chain_type_kwargs={"prompt": PROMPT}
    )

    result = qa_chain({"query": question})
    letter = result['result']

    #去掉所有换行符，防止分成多段消息
    letter = letter.replace('\n', ' ')
    letter = " ".join(letter.split())

    return letter
