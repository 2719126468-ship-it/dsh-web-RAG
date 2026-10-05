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
    assert 'expected = r.get("expect_answerability")' in SOURCE
    assert 'r.get("answerability_status") == expected' in SOURCE


def test_answerability_mode_is_explicitly_opt_in():
    assert 'os.getenv("EVALUATE_ANSWERABILITY", "false")' in SOURCE
    assert '"--answerability"' in SOURCE

    
def test_eval_sets_declare_explicit_answerability_verdicts():
    import json

    for name in ("test_set.json", "test_set_holdout.json"):
        path = ROOT / "rag-private-docs" / "eval" / name
        rows = json.loads(path.read_text(encoding="utf-8"))
        assert rows
        assert all(
            row.get("expect_answerability") in {"ANSWERABLE", "UNANSWERABLE"}
            for row in rows
        )
        assert all(
            row["expect_answerability"]
            == ("UNANSWERABLE" if row.get("expect_reject") else "ANSWERABLE")
            for row in rows
        )
