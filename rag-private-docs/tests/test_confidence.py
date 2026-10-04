"""Unit tests for the retrieval confidence contract."""

from pathlib import Path
import sys

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from confidence import RERANK_WEIGHT, RRF_WEIGHT, assign_confidence


def test_confidence_weights_form_a_convex_mix():
    assert RERANK_WEIGHT == 0.8
    assert RRF_WEIGHT == 0.2
    assert RERANK_WEIGHT + RRF_WEIGHT == 1.0


def test_confidence_uses_normalized_rrf_relative_to_returned_set():
    hits = [
        {"rerank_score": 0.5, "rrf_score": 0.01},
        {"rerank_score": 0.5, "rrf_score": 0.005},
    ]

    assign_confidence(hits)

    assert hits[0]["confidence"] == 0.8 * 0.5 + 0.2 * 1.0
    assert hits[1]["confidence"] == 0.8 * 0.5 + 0.2 * 0.5


def test_confidence_is_monotonic_in_rerank_score():
    low = [{"rerank_score": 0.2, "rrf_score": 0.01}]
    high = [{"rerank_score": 0.8, "rrf_score": 0.01}]

    assign_confidence(low)
    assign_confidence(high)

    assert 0.0 <= low[0]["confidence"] <= 1.0
    assert 0.0 <= high[0]["confidence"] <= 1.0
    assert high[0]["confidence"] > low[0]["confidence"]


def test_confidence_sanitizes_non_finite_rerank_scores():
    hits = [{"rerank_score": float("nan"), "rrf_score": 0.01}]

    assign_confidence(hits)

    assert hits[0]["confidence"] == 0.2


def test_fallback_confidence_stays_bounded():
    hits = [{"rrf_score": 0.08}, {"rrf_score": -1.0}]

    assign_confidence(hits)

    assert hits[0]["confidence"] == 0.8
    assert hits[1]["confidence"] == 0.0
