"""Confidence scoring helpers for retrieval results.

The confidence value is a heuristic retrieval signal, not a calibrated probability.
The reranker component is normalized to [0, 1] with sigmoid; the RRF component is
normalized relative to the returned candidate set.
"""

import math
from typing import Any, Dict, List

RERANK_WEIGHT = 0.8
RRF_WEIGHT = 0.2


def assign_confidence(final: List[Dict[str, Any]]) -> None:
    """Assign confidence from current rerank/RRF scores only."""
    if not final:
        return

    if "rerank_score" in final[0]:
        rrf_values = []
        for item in final:
            value = float(item.get("rrf_score", 0.0))
            rrf_values.append(value if math.isfinite(value) and value > 0 else 0.0)
        max_rrf = max(rrf_values, default=0.0)

        for item, rrf_value in zip(final, rrf_values):
            rerank_value = float(item.get("rerank_score", 0.0))
            if not math.isfinite(rerank_value):
                rerank_value = 0.0
            rerank_component = max(0.0, min(1.0, rerank_value))

            rrf_component = rrf_value / max_rrf if max_rrf > 0 else 0.0
            rrf_component = max(0.0, min(1.0, rrf_component))

            item["confidence"] = (
                RERANK_WEIGHT * rerank_component
                + RRF_WEIGHT * rrf_component
            )
        return

    for item in final:
        rrf_value = float(item.get("rrf_score", 0.0))
        if not math.isfinite(rrf_value):
            rrf_value = 0.0
        item["confidence"] = min(1.0, max(0.0, rrf_value * 10))
