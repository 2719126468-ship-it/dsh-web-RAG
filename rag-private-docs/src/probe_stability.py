"""Probe: LLM 自拒稳定性测试。

对每条负样本重复 N 次，看是否一致。
正样本作为对照（应稳定回答）。
输出 JSON 到当前目录。
"""
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qa import RAGEngine

RUNS = 5
REFUSE_MARKERS = ["未找到", "没有找到", "资料中未", "无法回答", "not found", "No relevant", "无法从"]

POSITIVE_SAMPLES = [
    "什么是 RAG？",
    "软件开发合同的总金额是多少？",
    "What are the authors of the synthetic study paper?",
]


def main():
    test_set_path = Path(__file__).resolve().parent.parent / "eval" / "test_set.json"
    test_set = json.loads(test_set_path.read_text(encoding="utf-8"))

    negatives = [
        (r["question"], r.get("negative_type", "negative"))
        for r in test_set if r.get("expect_reject")
    ]
    positives = [
        (r["question"], "positive")
        for r in test_set
        if not r.get("expect_reject") and r["question"] in POSITIVE_SAMPLES
    ]

    probes = negatives + positives
    print(f"=== probe stability: {len(probes)} questions x {RUNS} runs = {len(probes) * RUNS} calls ===")

    engine = RAGEngine(use_rerank=True)

    results = []
    for i, (q, typ) in enumerate(probes, 1):
        print(f"\n--- [{i}/{len(probes)}] [{typ}] {q}")
        for run in range(1, RUNS + 1):
            try:
                r = engine.query(q)
                ans = r["answer"]
                conf = r["confidence"]
                refused = any(m in ans for m in REFUSE_MARKERS)
                preview = ans[:120].replace("\n", " ")
                print(f"  run {run}/{RUNS}: refused={refused} conf={conf:.4f} | {preview}")
                results.append({
                    "question": q,
                    "type": typ,
                    "run": run,
                    "refused": refused,
                    "confidence": round(conf, 4),
                    "answer": ans[:300],
                })
            except Exception as e:
                print(f"  run {run}/{RUNS}: ERROR {e}")
                results.append({
                    "question": q,
                    "type": typ,
                    "run": run,
                    "error": str(e),
                })
            time.sleep(1)

    by_q = defaultdict(list)
    for r in results:
        if "refused" in r:
            by_q[(r["question"], r["type"])].append(r["refused"])

    summary = {}
    for (q, typ), refused_list in by_q.items():
        n = len(refused_list)
        n_refused = sum(refused_list)
        stable = len(set(refused_list)) == 1
        summary[q] = {
            "type": typ,
            "runs": n,
            "refused_count": n_refused,
            "refused_ratio": round(n_refused / n, 2) if n else 0.0,
            "stable": stable,
        }

    out = Path("probe_stability_results.json")
    out.write_text(
        json.dumps({"results": results, "summary": summary}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n=== 写入 {out} ===")
    print("\n=== 稳定性汇总 ===")
    for q, s in summary.items():
        marker = "STABLE" if s["stable"] else "UNSTABLE"
        print(f"  [{s['type']:30s}] [{marker:8s}] {s['refused_count']}/{s['runs']} refused | {q[:40]}")


if __name__ == "__main__":
    main()
