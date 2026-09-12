"""RAGAS 评估：用 LLM 当评委，量化 Faithfulness / Answer Relevancy / Context Recall。

依赖：pip install ragas datasets
用法：
    python eval_ragas.py eval/test_set.json eval/qa_results.json
"""
import json
import os
import sys
from pathlib import Path
from typing import Dict, List


def _check_deps():
    missing = []
    try:
        import ragas  # noqa: F401
    except ImportError:
        missing.append("ragas")
    try:
        import datasets  # noqa: F401
    except ImportError:
        missing.append("datasets")
    return missing


def load_json(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_dataset(test_set: List[Dict], qa_results: List[Dict]):
    from datasets import Dataset

    if len(test_set) != len(qa_results):
        print(f"[warn] 测试集 {len(test_set)} 条，结果 {len(qa_results)} 条，数量不一致，按较短的截断")
    n = min(len(test_set), len(qa_results))

    data = {
        "question": [test_set[i]["question"] for i in range(n)],
        "answer": [qa_results[i].get("answer", "") for i in range(n)],
        "contexts": [qa_results[i].get("contexts", []) for i in range(n)],
        "ground_truth": [
            test_set[i].get("ground_truth", "") or
            " ".join(test_set[i].get("ground_truth_keywords", []))
            for i in range(n)
        ],
    }
    return Dataset.from_dict(data)


def run_eval(test_set_path: str, qa_results_path: str) -> Dict:
    missing = _check_deps()
    if missing:
        print(f"[warn] 缺少依赖：{', '.join(missing)}")
        print(f"[warn] 安装：pip install {' '.join(missing)}")
        return {}

    from ragas import evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_recall,
    )

    test_set = load_json(test_set_path)
    qa_results = load_json(qa_results_path)
    dataset = build_dataset(test_set, qa_results)

    os.environ.setdefault("OPENAI_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
    os.environ.setdefault("OPENAI_BASE_URL", os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"))

    print("[info] 开始 RAGAS 评估...")
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_recall],
    )
    return dict(result)


def main():
    if len(sys.argv) < 3:
        print("用法：python eval_ragas.py eval/test_set.json eval/qa_results.json")
        sys.exit(1)

    result = run_eval(sys.argv[1], sys.argv[2])
    if not result:
        sys.exit(1)

    print()
    print("=" * 50)
    print("RAGAS 评估结果")
    print("=" * 50)
    for k, v in result.items():
        if isinstance(v, (int, float)):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")

    out = Path("ragas_results.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n详细结果已写入 {out}")


if __name__ == "__main__":
    main()
