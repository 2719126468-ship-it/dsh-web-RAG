"""第 4 课：完整 RAG 流程（端到端最小例子）

目标：
  - 把前面学的拼起来：文档 -> 切块 -> 嵌入 -> 检索 -> prompt -> LLM
  - 看到 RAG 回答与"裸 LLM 回答"在准确性上的差异

运行：
  python example_lessons/04_mini_rag.py
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.http import models

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_PATH = PROJECT_ROOT / "demo_rag_db"
COLLECTION = "lesson4"


def setup_store():
    """Build a tiny in-memory RAG store with 3 documents."""
    if DEMO_PATH.exists():
        shutil.rmtree(DEMO_PATH)
    docs = [
        Document(page_content=(
            "蓝海科技与码神信息于 2024-03-12 签订软件开发外包合同，"
            "项目为智能客服系统 v2.0，总金额 480,000 元，周期 90 天。"
        )),
        Document(page_content=(
            "延期罚则：每延期 1 天扣 0.5% 合同总额，最高不超过 10%。"
            "知识产权归甲方所有，乙方不得用于其他客户。"
        )),
        Document(page_content=(
            "莫干山徒步装备：登山鞋、速干衣、2L 水、能量棒、头灯、充电宝。"
            "山上农家乐午饭约 60 元/人。"
        )),
    ]
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-zh-v1.5",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    client = QdrantClient(path=str(DEMO_PATH))
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=models.VectorParams(size=512, distance=models.Distance.COSINE),
    )
    store = QdrantVectorStore(
        client=client, collection_name=COLLECTION, embedding=embeddings,
    )
    store.add_documents(docs)
    return store


def ask_with_rag(question: str, store, llm) -> str:
    """RAG: retrieve context, then ask LLM grounded on it."""
    docs = store.similarity_search(question, k=2)
    context = "\n\n".join(d.page_content for d in docs)
    prompt = f"""基于以下参考资料回答问题。如果资料中没提到，直接说不知道。

参考资料：
{context}

问题：{question}
"""
    return llm.invoke(prompt).content


def ask_without_rag(question: str, llm) -> str:
    """Plain LLM: no grounding, prone to hallucination."""
    return llm.invoke(question).content


def main():
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("[error] DEEPSEEK_API_KEY not set.")
        return

    store = setup_store()
    llm = ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL"),
        temperature=0,
    )

    questions = [
        "蓝海科技签订的软件合同金额是多少？",
        "合同延期罚则是怎样的？",
    ]
    for q in questions:
        print("=" * 60)
        print(f"Q: {q}")
        print("-" * 60)
        print(f"[无 RAG]  {ask_without_rag(q, llm)}")
        print()
        print(f"[有 RAG]  {ask_with_rag(q, store, llm)}")
        print()

    shutil.rmtree(DEMO_PATH)


if __name__ == "__main__":
    main()
