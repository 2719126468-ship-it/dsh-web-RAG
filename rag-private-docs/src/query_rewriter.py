"""Query rewriting: expand a user question into multiple search queries.

Why: a short query like "equipment" might miss the chunk that just says
"hiking shoes quick-dry shirt 2L water". If we also search for the
specific items, we catch both. The expanded queries are searched in
parallel and the results are merged via reciprocal rank fusion.

Uses an LLM to generate 2-3 alternative phrasings. Falls back to the
original query if no API key is available.
"""
import os
import re
from typing import List

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate


REWRITE_PROMPT = """You are a search query rewriter.

Given a user question, produce 2-3 alternative search queries that
would help retrieve relevant documents. Rules:
1. One query per line, no numbering or bullets
2. Same language as the original question
3. Different wording or angle; keep the meaning
4. If the question is vague, expand it to specific keywords the answer would contain
5. If the question is already specific, just produce 1-2 related variants

Original question: {question}

Rewritten queries:
"""


class QueryRewriter:
    def __init__(self, num_variants: int = 3):
        self.num_variants = num_variants
        self.prompt = ChatPromptTemplate.from_template(REWRITE_PROMPT)
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key or api_key.startswith("sk-xxxxxxx"):
            self.llm = None
        else:
            self.llm = ChatOpenAI(
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                api_key=api_key,
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
                temperature=0.3,
            )

    def rewrite(self, question: str) -> List[str]:
        """Return [original, *variants]. Always includes original first."""
        if not self.llm:
            # Fallback: simple keyword expansion for the most common patterns.
            # If the question contains a single vague noun, add a few common
            # specific terms that often appear with it. This is a very rough
            # approximation; with a real API key the LLM does much better.
            variants = self._fallback_rewrite(question)
            return [question] + variants
        try:
            resp = self.llm.invoke(self.prompt.format(question=question))
            text = resp.content if hasattr(resp, "content") else str(resp)
        except Exception as e:
            print(f"[warn] query rewrite failed: {e}")
            return [question]

        candidates = []
        for line in text.split("\n"):
            line = line.strip()
            line = re.sub(r"^[\-\*\d]+[.\):\s]+", "", line).strip()
            if line and line != question:
                candidates.append(line)
        variants = candidates[: self.num_variants]
        return [question] + variants

    # Keyword -> related keywords for the fallback (Chinese + English mixed)
    _EXPANSIONS = {
        "装备": ["登山鞋", "速干衣", "头灯", "水壶", "外套"],
        "equipment": ["hiking shoes", "tent", "stove", "water bottle"],
        "what": [],
        "合同": ["条款", "金额", "违约", "延期", "签约"],
        "contract": ["clause", "amount", "penalty", "deadline"],
        "上线": ["发布", "日期", "版本", "发布日"],
        "launch": ["release", "date", "version", "ship"],
        "API": ["调用", "endpoint", "key", "认证"],
        "金额": ["总价", "签约金", "费用", "支付"],
        "amount": ["total", "fee", "price", "payment"],
    }

    def _fallback_rewrite(self, q: str) -> List[str]:
        """Pick 2 variants by replacing a vague keyword with its common co-occurring terms."""
        import re as _re
        variants = []
        q_lower = q.lower()
        for kw, expansions in self._EXPANSIONS.items():
            if kw.lower() in q_lower and expansions:
                for term in expansions[:2]:
                    new_q = q.replace(kw, term, 1)
                    if new_q != q and new_q not in variants:
                        variants.append(new_q)
                if len(variants) >= self.num_variants:
                    break
        return variants[: self.num_variants]


def fuse_by_parent_id(hit_lists: List[List[dict]]) -> List[dict]:
    """Merge multiple hit lists, deduplicating by parent_id (or id).
    Uses RRF (reciprocal rank fusion).
    """
    score_by_key = {}
    items_by_key = {}
    for hits in hit_lists:
        for rank, h in enumerate(hits):
            meta = h.get("metadata", {})
            key = meta.get("parent_id") or h.get("id", str(id(h)))
            if key not in items_by_key:
                items_by_key[key] = h
            score_by_key.setdefault(key, 0.0)
            score_by_key[key] += 1.0 / (60 + rank + 1)
    ranked_keys = sorted(score_by_key, key=lambda k: score_by_key[k], reverse=True)
    return [items_by_key[k] for k in ranked_keys]


if __name__ == "__main__":
    rw = QueryRewriter()
    qs = rw.rewrite("What equipment do I need for hiking Moganshan?")
    print("Variants:")
    for q in qs:
        print(" -", q)