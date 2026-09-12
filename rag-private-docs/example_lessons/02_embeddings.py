"""第 2 课：Embeddings —— 把文字变成向量

目标：
  - 理解"嵌入向量"是什么
  - 用代码实际把一句话变成 512 维数字
  - 用余弦相似度比较两句话的语义距离

运行：
  python example_lessons/02_embeddings.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from langchain_huggingface import HuggingFaceEmbeddings


def cosine(a, b):
    """Cosine similarity between two vectors."""
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def main():
    print("Loading BGE embedding model (first run downloads ~100MB)...")
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-zh-v1.5",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    sentences = [
        "今天天气真好",
        "今日阳光明媚",
        "我午餐吃了红烧肉",
        "My favorite food is braised pork",
        "LangChain 是个开发 AI 应用的框架",
    ]
    vecs = embeddings.embed_documents(sentences)

    print(f"\n每句话被转成 {len(vecs[0])} 维向量")
    print(f"前 5 维示例: {vecs[0][:5]}\n")

    # Compare each pair
    print("=" * 60)
    print("余弦相似度（越大 = 越相似）")
    print("=" * 60)
    for i in range(len(sentences)):
        for j in range(i + 1, len(sentences)):
            s = cosine(vecs[i], vecs[j])
            bar = "█" * int(s * 30)
            print(f"{s:.3f}  {sentences[i][:20]:20s} <-> {sentences[j][:30]:30s} {bar}")


if __name__ == "__main__":
    main()
