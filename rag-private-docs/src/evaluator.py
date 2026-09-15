"""Lightweight RAG evaluator.

Implements two RAGAS-style retrieval metrics without external API calls:
  - context_precision:  fraction of retrieved chunks that contain keywords from the question
  - context_recall:     fraction of ground-truth keywords found in retrieved chunks

For answer faithfulness, see the separate eval_faithfulness.py (claim-level)
and eval_ragas.py (aggregate, requires ragas package).

Usage:
  python src/evaluator.py
  python src/evaluator.py --save     # 保存结果到 eval/results/
"""
import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Any

from retriever import HybridRetriever

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_SET_PATH = PROJECT_ROOT / "eval" / "test_set.json"
HOLDOUT_SET_PATH = PROJECT_ROOT / "eval" / "test_set_holdout.json"

# Must stay in sync with qa.py's CONFIDENCE_THRESHOLD.
# Negative samples (expect_reject=True) are "correct" when their top-1
# confidence falls below this threshold.
CONFIDENCE_THRESHOLD_FOR_EVAL = 0.30

# Default test set: 8 questions across 6 documents
DEFAULT_TEST_SET = [
    {
        "question": "什么是 RAG？",
        "ground_truth_keywords": ["检索增强生成", "RAG", "知识库", "向量"],
        "must_cite": "01-rag-intro.md",
    },
    {
        "question": "LangChain 有哪些文档加载器？",
        "ground_truth_keywords": ["TextLoader", "Markdown", "PDF", "Word"],
        "must_cite": "02-langchain-notes.md",
    },
    {
        "question": "DeepSeek 的 API 怎么调用？",
        "ground_truth_keywords": ["ChatOpenAI", "OpenAI", "兼容", "API"],
        "must_cite": "03-deepseek-api.md",
    },
    {
        "question": "软件开发合同的总金额是多少？",
        "ground_truth_keywords": ["480", "000", "金额", "合同"],
        "must_cite": "04-contract-2024-0312.md",
    },
    {
        "question": "莫干山徒步带什么装备？",
        "ground_truth_keywords": ["登山鞋", "水", "外套", "装备"],
        "must_cite": "05-weekend-hike-moganshan.md",
    },
    {
        "question": "12 月版本什么时候上线？",
        "ground_truth_keywords": ["12", "20", "上线", "双十二"],
        "must_cite": "06-email-client-dec-launch.md",
    },
    {
        "question": "合同延期罚则是怎样的？",
        "ground_truth_keywords": ["延期", "0.5", "10%"],
        "must_cite": "04-contract-2024-0312.md",
    },
    {
        "question": "客户希望 12 月版本提前几天？",
        "ground_truth_keywords": ["5", "提前", "12", "20"],
        "must_cite": "06-email-client-dec-launch.md",
    },
    # PDF-specific test questions (the synthetic two-column paper)
    {
        "question": "What is the title of the synthetic retrieval study paper?",
        "ground_truth_keywords": ["Synthetic", "Vector", "Retrieval"],
        "must_cite": "papers/test-two-column-paper.pdf",
    },
    {
        "question": "What does the paper say about Hit@1 reaching 1.0?",
        "ground_truth_keywords": ["Hit@1", "1.0", "op-1"],  # PDF says "op-1 ranking", not "top-1"
        "must_cite": "papers/test-two-column-paper.pdf",
    },
    {
        "question": "论文中关于 BM25 的描述是什么？",
        "ground_truth_keywords": ["BM25", "keyword"],
        "must_cite": "papers/test-two-column-paper.pdf",
    },
    {
        "question": "What are the authors of the synthetic study paper?",
        "ground_truth_keywords": ["Anonymous", "Authors"],
        "must_cite": "papers/test-two-column-paper.pdf",
    },
]


def _hits_keywords(text: str, keywords: List[str]) -> int:
    """Count how many keywords appear in the text (case-insensitive substring)."""
    text_l = text.lower()
    n = 0
    for kw in keywords:
        if kw.lower() in text_l:
            n += 1
    return n


def _get_text_for_metrics(hit: Dict) -> str:
    """Return the text to use for keyword-based metrics.

    With parent-child chunking, the hit.content is the short child (used for
    embedding/search), but the LLM actually sees the parent. Use parent_text
    when available so the metric reflects what the LLM uses.
    """
    meta = hit.get("metadata", {})
    parent = meta.get("parent_text", "")
    if parent:
        return parent
    return hit.get("content", "")


def context_precision(question: str, hits: List[Dict], keywords: List[str]) -> float:
    """Of the top-K retrieved chunks, what fraction contain at least one keyword?

    Uses parent_text (what the LLM actually reads) when available.
    """
    if not hits:
        return 0.0
    relevant = sum(
        1 for h in hits if _hits_keywords(_get_text_for_metrics(h), keywords) > 0
    )
    return relevant / len(hits)


def context_recall(hits: List[Dict], keywords: List[str]) -> float:
    """Fraction of ground-truth keywords found across all retrieved chunks.

    Uses parent_text (what the LLM actually reads) when available.
    """
    if not keywords:
        return 1.0
    combined = " ".join(_get_text_for_metrics(h) for h in hits)
    return _hits_keywords(combined, keywords) / len(keywords)


def hit_at_k(hits: List[Dict], must_cite, k: int = 5) -> bool:
    """Was at least one of the required sources among the top-k retrieved?

    must_cite can be a string (single source) or a list of strings
    (any match counts). This handles cases where the same fact appears
    in multiple documents (e.g. meeting notes + budget table).
    """
    if isinstance(must_cite, str):
        must_cite = [must_cite]
    top_k = hits[:k]
    for h in top_k:
        src = h.get("metadata", {}).get("source", "")
        for pat in must_cite:
            if pat in src:
                return True
    return False


def max_confidence(hits: List[Dict]) -> float:
    """Highest confidence across all hits (matches qa.py's rejection logic)."""
    if not hits:
        return 0.0
    return max((h.get("confidence", 0.0) for h in hits), default=0.0)


def answer_hit_at_k(hits: List[Dict], must_cite: str, k: int,
                    confidence_threshold: float) -> bool:
    """User-experience view: will the system actually answer with the right source?

    True only if (a) the required source is in top-k AND (b) max confidence
    across hits >= threshold. This mirrors what qa.py does: if max_conf is
    below the threshold, it replies "not found" regardless of source.
    """
    if max_confidence(hits) < confidence_threshold:
        return False
    return hit_at_k(hits, must_cite, k)


def evaluate(retriever: HybridRetriever, test_set: List[Dict] = None) -> Dict[str, Any]:
    """Run all test questions and compute aggregate metrics."""
    import os as _os
    if test_set is None:
        test_set = DEFAULT_TEST_SET
    use_rewrite = _os.getenv("USE_QUERY_REWRITE", "false").lower() == "true"
    rewriter = None
    fuser = None
    if use_rewrite:
        from query_rewriter import QueryRewriter, fuse_by_parent_id
        rewriter = QueryRewriter(num_variants=3)
        fuser = fuse_by_parent_id
    use_critic = _os.getenv("USE_CRITIC", "false").lower() == "true"
    critic = None
    if use_critic:
        from critic import RelevanceCritic, apply_critic
        critic = RelevanceCritic()
    rows = []
    for item in test_set:
        q = item["question"]
        kws = item["ground_truth_keywords"]
        must = item["must_cite"]
        if rewriter:
            queries = rewriter.rewrite(q)
            if len(queries) > 1:
                all_hits = [retriever.retrieve(qq, top_k=5) for qq in queries]
                hits = fuser(all_hits)
            else:
                hits = retriever.retrieve(q, top_k=5)
        else:
            hits = retriever.retrieve(q, top_k=5)
        if critic and hits:
            verdicts = critic.evaluate(q, hits)
            filtered, dropped = apply_critic(hits, verdicts, min_yes=2, maybe_penalty=1.0)
            if not filtered:
                # critic 全判 NO：保留 rerank top-1，但 confidence × 0.3
                top = max(hits, key=lambda x: x.get("confidence", 0))
                top["confidence"] = top.get("confidence", 0.0) * 0.3
                top["critic_verdict"] = "ALL_NO_PENALTY"
                print(f"  [critic] dropped all {len(hits)} chunks for: {q[:50]}")
                print(f"  [critic] keeping top-1 with confidence × 0.3 -> {top.get('confidence', 0):.4f}")
                hits = [top]
            else:
                if dropped:
                    print(f"  [critic] dropped {len(dropped)}/{len(hits)} chunks")
                hits = filtered
        row_confidence = max_confidence(hits)
        expect_reject = item.get("expect_reject", False)
        reject_correct = None
        if expect_reject:
            reject_correct = row_confidence < CONFIDENCE_THRESHOLD_FOR_EVAL
        rows.append({
            "question": q,
            "must_cite": must,
            "expect_reject": expect_reject,
            "confidence": round(row_confidence, 4),
            "reject_correct": reject_correct,
            "negative_type": item.get("negative_type"),
            "top1_source": hits[0].get("metadata", {}).get("source", "") if hits else "",
            "hit_at_1": hit_at_k(hits, must, k=1),
            "hit_at_3": hit_at_k(hits, must, k=3),
            "hit_at_5": hit_at_k(hits, must, k=5),
            "answer_hit_at_1": answer_hit_at_k(hits, must, 1, CONFIDENCE_THRESHOLD_FOR_EVAL),
            "answer_hit_at_3": answer_hit_at_k(hits, must, 3, CONFIDENCE_THRESHOLD_FOR_EVAL),
            "answer_hit_at_5": answer_hit_at_k(hits, must, 5, CONFIDENCE_THRESHOLD_FOR_EVAL),
            "context_precision": round(context_precision(q, hits, kws), 3),
            "context_recall": round(context_recall(hits, kws), 3),
        })
    positive_rows = [r for r in rows if not r.get("expect_reject")]
    negative_rows = [r for r in rows if r.get("expect_reject")]
    n_pos = len(positive_rows) or 1
    summary = {
        "num_questions": len(rows),
        "num_positive": len(positive_rows),
        "num_negative": len(negative_rows),
        "hit_at_1": round(sum(r["hit_at_1"] for r in positive_rows) / n_pos, 3) if positive_rows else 0.0,
        "hit_at_3": round(sum(r["hit_at_3"] for r in positive_rows) / n_pos, 3) if positive_rows else 0.0,
        "hit_at_5": round(sum(r["hit_at_5"] for r in positive_rows) / n_pos, 3) if positive_rows else 0.0,
        "context_precision": round(sum(r["context_precision"] for r in positive_rows) / n_pos, 3) if positive_rows else 0.0,
        "context_recall": round(sum(r["context_recall"] for r in positive_rows) / n_pos, 3) if positive_rows else 0.0,
    }
    if negative_rows:
        correct = sum(1 for r in negative_rows if r.get("reject_correct"))
        summary["reject_accuracy"] = round(correct / len(negative_rows), 3)
    summary["answer_hit_at_1"] = round(sum(r["answer_hit_at_1"] for r in positive_rows) / len(positive_rows), 3) if positive_rows else 0.0
    summary["answer_hit_at_3"] = round(sum(r["answer_hit_at_3"] for r in positive_rows) / len(positive_rows), 3) if positive_rows else 0.0
    summary["answer_hit_at_5"] = round(sum(r["answer_hit_at_5"] for r in positive_rows) / len(positive_rows), 3) if positive_rows else 0.0
        # 按 negative_type 分层统计（Part A）
    if negative_rows:
        by_type = {}
        for r in negative_rows:
            t = r.get("negative_type") or "untyped"
            by_type.setdefault(t, []).append(r)
        for t, rs in by_type.items():
            correct = sum(1 for r in rs if r.get("reject_correct"))
            summary["reject_accuracy_" + t] = round(correct / len(rs), 3)
            summary["num_negative_" + t] = len(rs)

    return {"summary": summary, "rows": rows}


def _save_result(result):
    """Save evaluation result to eval/results/ with timestamp filename."""
    import time
    results_dir = PROJECT_ROOT / "eval" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    out_file = results_dir / f"{timestamp}.json"
    payload = {
        "timestamp": timestamp,
        "summary": result["summary"],
        "rows": result["rows"],
    }
    out_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n结果已保存到 {out_file}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RAG 评估")
    parser.add_argument("--save", action="store_true", help="保存结果到 eval/results/")
    parser.add_argument("--holdout", action="store_true",
                        help="使用 hold-out 集，而不是调参集")
    args = parser.parse_args()

    if args.holdout:
        path = HOLDOUT_SET_PATH
        print(f"[info] 使用 hold-out 集：{path}")
    else:
        path = TEST_SET_PATH
        print(f"[info] 使用调参集：{path}")

    test_set = DEFAULT_TEST_SET
    if path.exists():
        test_set = json.loads(path.read_text(encoding="utf-8"))
    else:
        print(f"[warn] {path} 不存在，回退到硬编码 DEFAULT_TEST_SET")
    retriever = HybridRetriever(use_rerank=True)
    result = evaluate(retriever, test_set)
    print("\n" + "=" * 70)
    print("RAG 评估报告")
    print("=" * 70)
    print(f"\n问题数: {result['summary']['num_questions']}\n")
    for r in result["rows"]:
        status = "[OK]" if r["hit_at_1"] else ("[~]" if r["hit_at_3"] else "[X]")
        print(f"{status} Q: {r['question']}")
        print(f"   必须引用: {r['must_cite']} | Top-1: {r['top1_source']}")
        print(f"   hit@1={r['hit_at_1']} hit@3={r['hit_at_3']} hit@5={r['hit_at_5']} "
              f"precision={r['context_precision']} recall={r['context_recall']}")
    print("\n" + "-" * 70)
    print("汇总指标")
    print("-" * 70)
    for k, v in result["summary"].items():
        if k != "num_questions":
            print(f"  {k:25s} = {v}")

    if args.save:
        _save_result(result)

    return result


if __name__ == "__main__":
    main()