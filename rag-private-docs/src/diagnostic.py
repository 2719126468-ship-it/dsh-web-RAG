#!/usr/bin/env python3
"""
Pipeline Diagnostic Script — 快速检查系统状态

Run: python src/diagnostic.py

Checks:
  1. Qdrant collection size (should be ~44 for default test docs)
  2. BM25 retrieval (spot check)
  3. Dense retrieval (spot check)
  4. Hybrid retrieval (spot check)
  5. Reranker working
  6. Mini-evaluator (3 key questions)

Use this when:
  - Metrics look wrong (run it to catch stale index accumulation)
  - After changing chunking / retrieval settings
  - After a new ingest to verify it worked
"""

import sys
sys.path.insert(0, ".")

from pathlib import Path
import json

# ── 1. Collection size check ──────────────────────────────────────────────────

def check_collection(r):
    from retriever import HybridRetriever
    from config import config
    from qdrant_client import QdrantClient
    from pathlib import Path as P

    coll_name = r.client.get_collections().collections[0].name
    count_result = r.client.get_collection(coll_name)
    total_points = count_result.points_count

    # Expected: 44 child chunks for the default test set
    # (7 docs × ~6 children each, varies by content)
    expected_min = 30
    expected_max = 60

    status = "OK" if expected_min <= total_points <= expected_max else "WARN"
    print(f"  [{status}] Qdrant points: {total_points} (expected {expected_min}-{expected_max})")

    # Check for role distribution
    results = r.client.scroll(collection_name=coll_name, limit=200,
                                with_payload=True, with_vectors=False)
    roles = {}
    for pt in results[0]:
        role = pt.payload.get("metadata", {}).get("chunk_role", "?")
        roles[role] = roles.get(role, 0) + 1
    print(f"       Role distribution: {roles}")

    if total_points > expected_max * 1.5:
        print("       WARN: Points exceed expected range. Run: python src/indexer.py --force")
        print("             (Stale index accumulation detected)")

    return total_points

# ── 2. Retrieval spot checks ─────────────────────────────────────────────────

def check_bm25(r):
    from retriever import HybridRetriever

    q = "BM25 hybrid retrieval RAG"
    hits = r._bm25_search(q, top_n=5)
    print(f"  [OK] BM25 search: top hit = {hits[0].get('metadata',{}).get('source','?')[-40:]} "
          f"(score={hits[0].get('bm25_score', 0):.3f})")
    return True

def check_dense(r):
    from retriever import HybridRetriever

    q = "BM25 hybrid retrieval RAG"
    hits = r._dense_search(q, top_n=5)
    print(f"  [OK] Dense search: top hit = {hits[0].get('metadata',{}).get('source','?')[-40:]} "
          f"(score={hits[0].get('dense_score', 0):.4f})")
    return True

def check_hybrid(r):
    from retriever import HybridRetriever

    q = "BM25 hybrid retrieval"
    hits = r.retrieve(q, top_k=3)
    confs = [h.get("confidence", 0) for h in hits]
    print(f"  [OK] Hybrid retrieval: top-3 conf = {[f'{c:.3f}' for c in confs]}")
    return all(0 <= c <= 1 for c in confs)

def check_reranker(r):
    from retriever import HybridRetriever

    q = "BM25 hybrid retrieval"
    hits = r._bm25_search(q, top_n=10)
    candidates = [{**h, "rerank_score": 0.0} for h in hits]

    # Check reranker scores are different (meaning it's working)
    reranked = r._rerank(q, candidates, top_n=5)
    scores = [h.get("rerank_score", 0) for h in reranked]

    # Reranker should produce a ranking (scores should NOT all be 0)
    spread = max(scores) - min(scores)
    ok = spread > 0.001
    status = "OK" if ok else "WARN"
    print(f"  [{status}] Reranker: score spread = {spread:.4f} (should be > 0)")
    if not ok:
        print("         Reranker may not be working — check BGE reranker model installation")
    return ok

# ── 3. Mini evaluator ─────────────────────────────────────────────────────────

def check_mini_eval(r):
    from retriever import HybridRetriever

    # 3 key questions from the test set
    questions = [
        ("BM25 检索方法", "papers/test-two-column-paper.pdf", 5),
        ("合同 延期 罚则", "docs/04-contract-2024-0312.md", 5),
        ("synthetic study authors", "papers/test-two-column-paper.pdf", 3),
    ]

    all_pass = True
    for q, must_cite, k in questions:
        hits = r.retrieve(q, top_k=k)
        top_src = hits[0].get("metadata", {}).get("source", "") if hits else ""
        hit_top1 = must_cite in top_src
        status = "PASS" if hit_top1 else "FAIL"
        print(f"  [{status}] Q='{q}' top-1={top_src[-35:]}")
        if not hit_top1:
            all_pass = False

    return all_pass

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 60)
    print("  RAG Pipeline Diagnostic")
    print("=" * 60)
    print()

    from retriever import HybridRetriever
    r = HybridRetriever()

    checks = [
        ("1. Qdrant Collection", check_collection),
        ("2. BM25 Search", check_bm25),
        ("3. Dense Search", check_dense),
        ("4. Hybrid Retrieval", check_hybrid),
        ("5. Reranker", check_reranker),
        ("6. Mini Evaluator", check_mini_eval),
    ]

    results = {}
    for name, fn in checks:
        print(f"[{name}]")
        try:
            results[name] = fn(r)
        except Exception as e:
            print(f"  [ERROR] {e}")
            results[name] = False
        print()

    # Summary
    print("=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"  Summary: {passed}/{total} checks passed")
    if passed == total:
        print("  Status: ALL GREEN — pipeline is healthy")
        print()
        print("  Run full evaluator: cd src && python evaluator.py")
    else:
        print("  Status: WARN — some checks failed, see above")
        print()
        print("  If collection size is wrong, try: python src/indexer.py --force")
    print("=" * 60)

if __name__ == "__main__":
    main()
