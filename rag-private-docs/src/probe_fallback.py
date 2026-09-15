"""One-shot probe: does the LLM self-refuse off-topic questions
when rerank is disabled (so confidence-based rejection is unreliable)?

Read the printed answers. This is a probe, not a test.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qa import RAGEngine

PROBES = [
    ("off_topic", "公司年假有多少天？"),
    ("off_topic", "Python 的 GIL 是什么？"),
    ("topic_rel", "合同的违约金是多少？"),
    ("topic_rel", "莫干山徒步路线全长多少公里？"),
    ("positive", "软件开发合同的总金额是多少？"),
]

REFUSE_MARKERS = ["未找到", "没有找到", "资料中未", "无法回答", "not found", "No relevant", "无法从"]

def main():
    engine = RAGEngine(use_rerank=True)
    print("=" * 72)
    print("Probe: LLM self-refusal when rerank is disabled")
    print("=" * 72)
    print(f"use_rerank = {engine.retriever.use_rerank}")
    print(f"_reranker  = {engine.retriever._reranker}")
    print()
    for kind, q in PROBES:
        r = engine.query(q)
        ans = r["answer"]
        conf = r["confidence"]
        refused = any(m in ans for m in REFUSE_MARKERS)
        tag = "REFUSED" if refused else "ANSWERED"
        print(f"[{kind:9s}] [{tag:8s}] conf={conf:.4f}")
        print(f"  Q: {q}")
        print(f"  A: {ans[:400]}")
        print()

if __name__ == "__main__":
    main()
