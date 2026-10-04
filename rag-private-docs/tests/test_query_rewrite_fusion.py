"""Tests for query-rewrite fusion score hygiene."""

from pathlib import Path
import sys

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from query_rewriter import fuse_by_parent_id


def test_fusion_assigns_fresh_rrf_and_removes_stale_scores():
    hits = [
        [
            {
                "id": "a",
                "content": "first",
                "metadata": {"parent_id": "p1"},
                "rerank_score": 0.91,
                "confidence": 0.88,
            },
            {
                "id": "b",
                "content": "second",
                "metadata": {"parent_id": "p2"},
            },
        ],
        [
            {
                "id": "c",
                "content": "same parent",
                "metadata": {"parent_id": "p1"},
                "rerank_score": 0.12,
                "confidence": 0.11,
            }
        ],
    ]

    fused = fuse_by_parent_id(hits)

    assert len(fused) == 2
    assert fused[0]["metadata"]["parent_id"] == "p1"
    assert fused[0]["rrf_score"] == 1 / 61 + 1 / 61
    assert "rerank_score" not in fused[0]
    assert "confidence" not in fused[0]
    assert fused[1]["rrf_score"] == 1 / 62
