"""
用户上传 resume.pdf
      ↓
→ 生成文件 hash（MD5）
      ↓
→ 查本地向量库是否已有对应 hash 的目录
      ↓
   ↙                ↘
已存在             不存在 or hash 变了
  ↓                        ↓
加载已有向量库      → 重新向量化 → 保存
"""

import hashlib
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

EMBED_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
COLLECTION_NAME = "resume"

_embedder: SentenceTransformer | None = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL_NAME)
    return _embedder


def text_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:
    if chunk_size <= chunk_overlap:
        raise ValueError("chunk_size must exceed chunk_overlap")
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == n:
            break
        start = end - chunk_overlap
    return chunks


class VectorStore:
    """Chroma collection wrapper with semantic search over PDF chunks."""

    def __init__(self, collection: chromadb.Collection):
        self._collection = collection

    def search(self, query: str, k: int = 4) -> list[str]:
        query_embedding = _get_embedder().encode([query]).tolist()
        results = self._collection.query(query_embeddings=query_embedding, n_results=k)
        documents = results.get("documents") or []
        return documents[0] if documents else []

    def check_relevance(self, query: str, distance_threshold: float = 1.3) -> tuple[bool, float]:
        """检查查询（如JD）与集合的最短距离。
        distance_threshold 默认1.3（经验值，基于 L2 距离，越小越相似）。
        如果所有 chunk 的距离都大于阈值，说明完全不相关，返回 False。
        """
        query_embedding = _get_embedder().encode([query]).tolist()
        results = self._collection.query(query_embeddings=query_embedding, n_results=1)
        distances = results.get("distances")
        if not distances or not distances[0]:
            return True, 0.0  # 没提取到 distance 就放行
        
        min_distance = distances[0][0]
        return min_distance <= distance_threshold, min_distance


def embed_resume(resume_text: str, base_dir: str = "./vectorstores") -> VectorStore:
    file_id = text_hash(resume_text)
    persist_dir = Path(base_dir) / file_id
    persist_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(persist_dir))
    existing = {c.name for c in client.list_collections()}

    if COLLECTION_NAME in existing:
        print("✅ 加载已存在向量库")
        collection = client.get_collection(COLLECTION_NAME)
    else:
        print("❌ 不存在向量库，重新向量化")
        chunks = split_text(resume_text)
        if not chunks:
            raise ValueError("No text extracted from resume")

        embeddings = _get_embedder().encode(chunks).tolist()
        collection = client.create_collection(COLLECTION_NAME)
        collection.add(
            documents=chunks,
            embeddings=embeddings,
            ids=[f"chunk-{i}" for i in range(len(chunks))],
        )
        print(f"✅ 已保存向量库到：{persist_dir}")

    return VectorStore(collection)
