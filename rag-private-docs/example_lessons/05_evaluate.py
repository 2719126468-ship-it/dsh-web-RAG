"""第 5 课：评估你的 RAG 系统

目标：
  - 写一个 ground-truth 测试集
  - 跑评估，看 hit@K / context_precision / context_recall
  - 理解这些指标在工程上的意义

运行：
  python example_lessons/05_evaluate.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from retriever import HybridRetriever
from evaluator import evaluate


def main():
    print("Loading hybrid retriever (this includes the reranker, ~700MB)...")
    print("Pass use_rerank=False to skip the reranker if needed.\n")
    retriever = HybridRetriever(use_rerank=True)

    custom_test = [
        {
            "question": "蓝海科技签的合同金额是多少？",
            "ground_truth_keywords": ["480", "000", "合同"],
            "must_cite": "04-contract-2024-0312.md",
        },
        {
            "question": "莫干山徒步要带什么？",
            "ground_truth_keywords": ["登山鞋", "水", "外套"],
            "must_cite": "05-weekend-hike-moganshan.md",
        },
    ]

    result = evaluate(retriever, custom_test)
    print(f"\n问题数: {result['summary']['num_questions']}")
    for k, v in result["summary"].items():
        if k != "num_questions":
            print(f"  {k:25s} = {v}")


if __name__ == "__main__":
    main()
