from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
"""
用户上传 resume.pdf
      ↓
→ 生成文件 hash（比如 MD5）
      ↓
→ 查本地向量库是否已有对应 hash 的文件夹
      ↓
   ↙                ↘
已存在             不存在 or hash 变了
  ↓                        ↓
加载已有向量库      → 重新向量化 → 保存

"""
import hashlib

def file_hash(filepath: str) -> str:
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

from pathlib import Path

def check_vectorstore_exists(hash: str, base_dir: str = "./vectorstores") -> bool:
    # Chroma 持久化时会生成 chroma.sqlite 文件
    return Path(f"{base_dir}/{hash}/chroma.sqlite").exists()


def embed_pdf(file_path: str, base_dir: str = "./vectorstores") -> Chroma:
    file_id = file_hash(file_path)
    save_path = f"{base_dir}/{file_id}"

    # 向量化（通用模型）
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")

    if check_vectorstore_exists(file_id, base_dir):
        print("✅ 加载已存在向量库")
        vectorstore = Chroma(
            persist_directory=save_path,
            embedding_function=embeddings,
        )
    else:
        print("❌ 不存在向量库，重新向量化")
        # 加载 PDF 文本
        loader = PyPDFLoader(file_path)
        docs = loader.load()

        # 文本切片
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = splitter.split_documents(docs)


        # 存入向量库（可持久化
        vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=save_path
        )
        print("✅ 已保存向量库到：",save_path)  # 保存
    return vectorstore
