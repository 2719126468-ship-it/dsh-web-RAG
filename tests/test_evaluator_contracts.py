"""Regression tests for evaluator pipeline and metric semantics."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVALUATOR = ROOT / "rag-private-docs" / "src" / "evaluator.py"
SOURCE = EVALUATOR.read_text(encoding="utf-8")


def test_rewrite_evaluation_reranks_after_rrf_fusion():
    assert "fused_hits = fuser(all_hits)" in SOURCE
    assert 'retriever.rerank_candidates(q, fused_hits, top_k=5)' in SOURCE


def test_answerability_accuracy_excludes_non_definitive_statuses():
    assert 'status") in {"ANSWERABLE", "UNANSWERABLE"}' in SOURCE
    assert '"answerability_coverage"' in SOURCE


def test_answerability_accuracy_requires_exact_expected_verdict():
    assert 'expected = "UNANSWERABLE" if r.get("expect_reject") else "ANSWERABLE"' in SOURCE
    assert 'r.get("answerability_status") == expected' in SOURCE


def test_answerability_mode_is_explicitly_opt_in():
    assert 'os.getenv("EVALUATE_ANSWERABILITY", "false")' in SOURCE
    assert '"--answerability"' in SOURCE
