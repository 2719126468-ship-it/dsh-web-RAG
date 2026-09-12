"""CRAG: Corrective RAG -- evaluate retrieved chunks before using them.

Idea (Microsoft, 2024):
  Standard RAG: question -> retrieve -> LLM
  CRAG: question -> retrieve -> evaluator -> LLM
  Evaluator scores each chunk "relevant" / "ambiguous" / "irrelevant".
  - Relevant: keep as-is
  - Irrelevant: drop
  - Ambiguous: keep, but also trigger a refined-query re-retrieval

Why: even with good retrieval, ~20-30% of Top-5 chunks are off-topic.
  Filtering them gives the LLM a cleaner context, improving precision.

Fallback: when no LLM API key is available, skip the evaluator and
  use whatever was retrieved. This loses the precision boost but keeps
  the system running.
"""
import os
from typing import List, Dict, Any, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate


EVAL_PROMPT = """You are evaluating whether a retrieved document chunk is relevant to a user's question.

For each chunk, output a single token on its own line:
  YES  -- the chunk contains facts that help answer the question
  NO   -- the chunk is clearly unrelated
  MAYBE-- the chunk is topically related but does not directly answer

Be strict. "NO" if the chunk is from a different topic entirely.
Output only YES / NO / MAYBE, one per line, in the same order.

Question: {question}

Chunks:
{chunks}

Verdicts:
"""


def _get_critic_text(hit: Dict, max_len: int = 500) -> str:
    """Text used for critic evaluation.

    Priority: parent_text (what the LLM actually reads) > content (child).
    This aligns critic decisions with the final LLM input. Using child-only
    was a bug: a child may be a narrow fragment while its parent holds the
    actual answer.
    """
    meta = hit.get("metadata", {})
    parent = meta.get("parent_text", "")
    text = parent if parent else hit.get("content", "")
    return text[:max_len].replace("\n", " ")


class RelevanceCritic:
    """Score retrieved chunks as YES/NO/MAYBE relative to the question."""

    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key or api_key.startswith("sk-xxxxxxx"):
            self.llm = None
        else:
            self.llm = ChatOpenAI(
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                api_key=api_key,
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
                temperature=0.0,
            )
        self.prompt = ChatPromptTemplate.from_template(EVAL_PROMPT)

    def evaluate(self, question: str, hits: List[Dict]) -> List[str]:
        """Return a list of "YES"/"NO"/"MAYBE" matching the input order.

        Without an LLM, fall back to a simple heuristic: if a hit's
        confidence is below MIN_CONFIDENCE, mark it NO. This still drops
        the worst-offending chunks without spending API calls.
        """
        if not hits:
            return []
        if not self.llm:
            # Heuristic: low confidence = NO
            MIN_CONF = 0.10
            return ["NO" if h.get("confidence", 0) < MIN_CONF else "YES" for h in hits]
        previews = [_get_critic_text(h) for h in hits]
        chunks_text = "\n".join(f"[{i+1}] {p}" for i, p in enumerate(previews))
        try:
            resp = self.llm.invoke(self.prompt.format(question=question, chunks=chunks_text))
            text = resp.content if hasattr(resp, "content") else str(resp)
        except Exception as e:
            print(f"[warn] critic failed: {e}; skipping filter")
            return ["YES"] * len(hits)
        verdicts = []
        for line in text.split("\n"):
            line = line.strip().upper()
            if line.startswith("YES"):
                verdicts.append("YES")
            elif line.startswith("NO"):
                verdicts.append("NO")
            elif line.startswith("MAYBE"):
                verdicts.append("MAYBE")
            else:
                verdicts.append("YES")
        while len(verdicts) < len(hits):
            verdicts.append("YES")
        return verdicts[: len(hits)]


def apply_critic(hits: List[Dict], verdicts: List[str], min_yes: int = 2) -> Tuple[List[Dict], List[Dict]]:
    """Apply verdicts to hits.

    Returns (kept, dropped) where kept is the filtered list and dropped
    is the chunks we removed (kept around for debugging).
    """
    if len(hits) != len(verdicts):
        return hits, []
    kept = []
    dropped = []
    maybe = []
    for h, v in zip(hits, verdicts):
        if v == "NO":
            dropped.append(h)
        elif v == "MAYBE":
            maybe.append(h)
        else:  # YES
            kept.append(h)
    if len(kept) + len(maybe) < min_yes:
        kept = kept + maybe
        maybe = []
    return kept, dropped


if __name__ == "__main__":
    print("Critic is meant to be called from qa.py / evaluator.py.")