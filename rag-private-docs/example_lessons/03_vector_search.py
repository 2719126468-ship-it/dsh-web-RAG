"""第 3 课：向量检索 —— 找最相似的文档

目标：
  - 把 N 个文档嵌入并存入 Qdrant
  - 用一个 query 找出最相似的 Top-K
  - 看到"语义匹配"与"关键词匹配"的差异

运行：
  python example_lessons/03_vector_search.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_PATH = PROJECT_ROOT / "demo_vector_db"
COLLECTION = "lesson3"


def main():
    # 1) Fresh database
    if DEMO_PATH.exists():
        shutil.rmtree(DEMO_PATH)

    docs = [
        Document(page_content="苹果是一种水果，颜色通常是红色或绿色。",
                 metadata={"topic": "水果"}),
        Document(page_content="香蕉富含钾，是运动员喜欢的能量来源。",
                 metadata={"topic": "水果"}),
        Document(page_content="深度学习是机器学习的一个分支，使用神经网络。",
                 metadata={"topic": "AI"}),
        Document(page_content="Python 是一种广泛使用的高级编程语言。",
                 metadata={"topic": "编程"}),
        Document(page_content="如何训练一个 RAG 系统？先嵌入文档再存入向量库。",
                 metadata={"topic": "AI"}),
    ]

    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-zh-v1.5",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    # Pre-create the collection
    client = QdrantClient(path=str(DEMO_PATH))
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=models.VectorParams(size=512, distance=models.Distance.COSINE),
    )

    store = QdrantVectorStore(
        client=client, collection_name=COLLECTION, embedding=embeddings,
    )
    store.add_documents(docs)
    print(f"Indexed {len(docs)} documents\n")

    # 2) Run queries
    queries = [
        "推荐一种健康的水果",
        "AI 怎么学？",
        "LangChain 怎么用？",
        "如何做 embedding？",
    ]
    for q in queries:
        print(f"Q: {q}")
        results = store.similarity_search_with_score(q, k=2)
        for doc, score in results:
            print(f"  [{score:.3f}] ({doc.metadata['topic']}) {doc.page_content[:50]}")
        print()

    # Cleanup
    shutil.rmtree(DEMO_PATH)


if __name__ == "__main__":
    main()
