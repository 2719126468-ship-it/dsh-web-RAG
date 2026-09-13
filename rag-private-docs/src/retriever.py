"""Hybrid retriever: BM25 + dense + reranking.

Pipeline:
  1. BM25 returns top-20 keyword matches
  2. Dense vector returns top-20 semantic matches
  3. Reciprocal Rank Fusion (RRF) merges the two lists
  4. Optional: BGE cross-encoder reranks the merged top-20
  5. Return top-K with similarity scores
"""
import math
import re
from pathlib import Path
from typing import List, Dict, Any

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from rank_bm25 import BM25Okapi

from qdrant_factory import create_qdrant_client

from config import config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QDRANT_PATH = PROJECT_ROOT / config.QDRANT_PATH.lstrip("./")


def _tokenize(text: str) -> List[str]:
    """Simple mixed CJK + ASCII tokenizer.

    For Chinese: emit each char + 2-gram shards for short queries.
    For ASCII: split on whitespace and punctuation.
    """
    text = text.lower()
    tokens = []
    # ASCII words
    for w in re.findall(r"[a-z0-9_]+", text):
        tokens.append(w)
    # Single Chinese chars
    for ch in re.findall(r"[\u4e00-\u9fff]", text):
        tokens.append(ch)
    # Chinese bigrams (improves recall for compound terms)
    cjk = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    for i in range(len(cjk) - 1):
        tokens.append(cjk[i:i+2])
    return tokens


class HybridRetriever:
    """Combines BM25 and dense retrieval, optionally with reranking."""

    def __init__(self, use_rerank: bool = True, rrf_k: int = 60):
        print("[info] Loading embedding model...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=config.EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        self.client = create_qdrant_client()
        self.store = QdrantVectorStore(
            client=self.client,
            collection_name=config.COLLECTION_NAME,
            embedding=self.embeddings,
        )
        self.use_rerank = use_rerank
        self.rrf_k = rrf_k
        self._bm25 = None
        self._bm25_corpus: List[Dict[str, Any]] = []
        self._reranker = None

    def _load_reranker(self):
        if self._reranker is not None:
            return self._reranker
        if not self.use_rerank:
            return None
        try:
            from sentence_transformers import CrossEncoder
            print("[info] Loading reranker (BGE-reranker-base)...")
            self._reranker = CrossEncoder("BAAI/bge-reranker-base")
        except Exception as e:
            print(f"[warn] Reranker unavailable, skipping: {e}")
            self._reranker = None
        return self._reranker

    def _load_bm25(self):
        """Build BM25 index from all points in the Qdrant store."""
        if self._bm25 is not None:
            return self._bm25
        print("[info] Building BM25 index from Qdrant points...")
        points, _ = self.client.scroll(
            collection_name=config.COLLECTION_NAME,
            limit=10000,
            with_payload=True,
            with_vectors=False,
        )
        corpus = []
        for p in points:
            payload = p.payload or {}
            content = payload.get("page_content", "")
            meta = payload.get("metadata", {})
            corpus.append({"id": str(p.id), "content": content, "metadata": meta})
        if not corpus:
            print("[warn] Empty collection — BM25 index will be empty")
            self._bm25 = BM25Okapi([["__empty__"]])
            self._bm25_corpus = []
            return self._bm25
        tokenized_corpus = [_tokenize(c["content"]) for c in corpus]
        self._bm25 = BM25Okapi(tokenized_corpus)
        self._bm25_corpus = corpus
        print(f"[info] BM25 index built with {len(corpus)} documents")
        return self._bm25

    @staticmethod
    def _rrf_score(rank: int, k: int = 60) -> float:
        return 1.0 / (k + rank + 1)

    def _bm25_search(self, query: str, top_n: int = 20) -> List[Dict[str, Any]]:
        bm25 = self._load_bm25()
        if not self._bm25_corpus:
            return []
        tokens = _tokenize(query)
        if not tokens:
            return []
        scores = bm25.get_scores(tokens)
        ranked = sorted(
            enumerate(scores), key=lambda x: x[1], reverse=True
        )

        # Normalize BM25 scores per source so no single document dominates.
        # Problem: a 1500-char RAG intro has more query tokens than a 200-char
        # PDF chunk → inflated BM25 scores across all its children.
        # Fix: for each source, divide all scores by that source's max score
        # so each source contributes at most 1.0 to the RRF fusion.
        # Compute max per source from top-N to avoid O(n*k) grouping of all docs.
        source_max: dict[str, float] = {}
        for idx, score in ranked[:100]:  # sample top 100 for max-per-source
            doc = self._bm25_corpus[idx]
            src = doc["metadata"].get("source", "__unknown__")
            if src not in source_max or score > source_max[src]:
                source_max[src] = score

        results = []
        for idx, score in ranked[:top_n]:
            doc = self._bm25_corpus[idx]
            src = doc["metadata"].get("source", "__unknown__")
            max_s = source_max.get(src, 1.0)
            normalized = float(score) / max_s if max_s > 0 else 0.0
            results.append({
                "id": doc["id"],
                "content": doc["content"],
                "metadata": doc["metadata"],
                "bm25_score": normalized,
            })
        return results

    def _dense_search(self, query: str, top_n: int = 20) -> List[Dict[str, Any]]:
        query_vector = self.embeddings.embed_query(query)
        # qdrant-client >= 1.10 推荐用 query_points 替代已弃用的 search
        response = self.client.query_points(
            collection_name=config.COLLECTION_NAME,
            query=query_vector,
            limit=top_n,
            with_payload=True,
        )
        points = getattr(response, "points", response)
        out = []
        for r in points:
            payload = r.payload or {}
            out.append({
                "id": str(r.id),
                "content": payload.get("page_content", ""),
                "metadata": payload.get("metadata", {}),
                "dense_score": float(r.score),
            })
        return out

    def _rerank(
        self, query: str, candidates: List[Dict[str, Any]], top_n: int
    ) -> List[Dict[str, Any]]:
        reranker = self._load_reranker()
        if reranker is None or not candidates:
            return candidates[:top_n]
        pairs = [[query, c["content"]] for c in candidates]
        scores = reranker.predict(pairs)
        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)
        ranked = sorted(candidates, key=lambda x: x.get("rerank_score", 0), reverse=True)
        return ranked[:top_n]

    def retrieve(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """Run full hybrid retrieval pipeline."""
        if top_k is None:
            top_k = config.TOP_K
        # Step 1+2: parallel-ish retrieval from both indexes
        bm25_hits = self._bm25_search(query, top_n=20)
        dense_hits = self._dense_search(query, top_n=20)

        # Step 3: RRF fusion
        fused: Dict[str, Dict[str, Any]] = {}
        for rank, hit in enumerate(bm25_hits):
            fid = hit["id"]
            if fid not in fused:
                fused[fid] = {**hit, "rrf_score": 0.0}
            fused[fid]["rrf_score"] += self._rrf_score(rank, self.rrf_k)
        for rank, hit in enumerate(dense_hits):
            fid = hit["id"]
            if fid not in fused:
                fused[fid] = {**hit, "rrf_score": 0.0}
            fused[fid]["rrf_score"] += self._rrf_score(rank, self.rrf_k)

        merged = sorted(fused.values(), key=lambda x: x["rrf_score"], reverse=True)
        # Take top 30 for rerank (larger pool = more diverse candidates for reranker to choose from)
        candidates = merged[:30]

        # Step 4: rerank
        final = self._rerank(query, candidates, top_n=top_k)

        # Normalize confidence to 0-1 range.
        # Strategy: blend rerank score (cross-encoder semantic judgment) with rrf_score
        # (hybrid retrieval authority). This gives the reranker dominant weight while
        # preserving document-level signal from the RRF score.
        if final and "rerank_score" in final[0]:
            max_rerank = max(c.get("rerank_score", 0) for c in final)
            max_rrf = max(c.get("rrf_score", 0) for c in final)
            for c in final:
                r_score = c.get("rerank_score", 0) / max_rerank if max_rerank > 0 else 0
                rf = c.get("rrf_score", 0) / max_rrf if max_rrf > 0 else 0
                # 80% rerank, 20% rrf — reranker dominates, RRF provides doc authority
                c["confidence"] = 0.8 * r_score + 0.2 * rf
        else:
            for c in final:
                c["confidence"] = min(1.0, c.get("rrf_score", 0) * 10)
        return final

    def format_for_llm(self, hits: List[Dict[str, Any]]) -> str:
        """Format retrieved docs into a context block for the LLM prompt.

        Parent-child mode: if a hit has parent_text in metadata, use the
        parent (broader context) instead of the child (narrow match).
        """
        blocks = []
        seen_parents = set()  # avoid duplicating the same parent
        idx = 0
        for h in hits:
            meta = h.get("metadata", {})
            src = meta.get("source", "unknown")
            conf = h.get("confidence", 0)
            parent_text = meta.get("parent_text")
            parent_id = meta.get("parent_id")

            if parent_text and parent_id:
                # Parent-child mode: show parent once, but only if not already shown
                if parent_id in seen_parents:
                    continue
                seen_parents.add(parent_id)
                idx += 1
                content_to_show = parent_text
                tag = f"[{idx}] {src} (parent chunk, 置信度: {conf:.2f})"
            else:
                idx += 1
                content_to_show = h.get("content", "")
                tag = f"[{idx}] {src} (置信度: {conf:.2f})"
            blocks.append(tag + "\n" + content_to_show.strip())
        return "\n\n".join(blocks)
