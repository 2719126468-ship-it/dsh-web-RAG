"""RAG engine v2: multi-turn chat + hybrid retrieval + strict anti-hallucination."""
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from config import config
from retriever import HybridRetriever
from outline import PROJECT_ROOT, find_heading_at_line, snippet_with_context

CONFIDENCE_THRESHOLD = 0.30

STRICT_SYSTEM_PROMPT = """你是私人知识库问答助手。
你的回答必须**严格基于**"参考资料"中的事实，绝不编造任何数字、日期、人名、合同条款。

规则：
1. 只能使用参考资料中明确写出的事实。
2. 用 [1][2] 角标标注引用，编号对应参考资料列表。
3. 如果参考资料与问题无关或置信度低，直接说"资料中未找到相关内容"，不要猜测。
4. 回答要简洁准确：先直接答案，再列关键引用。
5. 如果用户问题是对话历史中的追问（如"那第二条呢"、"具体说说"），结合上下文理解，但答案仍必须基于参考资料。
"""

USER_TEMPLATE = """【参考资料】
{context}

【对话历史】
{history}

【当前问题】
{question}
"""


def format_history(messages: List[Dict[str, str]], max_turns: int = 4) -> str:
    """Render the last N turns as a compact history block."""
    recent = messages[-max_turns*2:] if messages else []
    lines = []
    for m in recent:
        role = "用户" if m["role"] == "user" else "助手"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines) if lines else "(无历史)"


class RAGEngine:
    def __init__(self, use_rerank: bool = True):
        self.retriever = HybridRetriever(use_rerank=use_rerank)
        if not config.DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY missing. Set it in .env")
        self.llm = ChatOpenAI(
            model=config.DEEPSEEK_MODEL,
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
            temperature=0.1,
        )

    def retrieve(self, question: str, top_k: int = None) -> List[Dict[str, Any]]:
        return self.retriever.retrieve(question, top_k=top_k)

    def query(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
        top_k: int = None,
    ) -> Dict[str, Any]:
        """Run a single turn; history is a list of {role, content} dicts."""
        history = history or []

        # Multi-query expansion: rewrite the question into 2-3 variants and
        # search each in parallel, then fuse by parent_id.
        if os.getenv("USE_QUERY_REWRITE", "false").lower() == "true":
            try:
                from query_rewriter import QueryRewriter, fuse_by_parent_id
                rw = QueryRewriter(num_variants=3)
                queries = rw.rewrite(question)
                if len(queries) > 1:
                    print(f"[rewrite] {len(queries)} variants: {queries}")
                    all_hits = [self.retrieve(q, top_k=top_k) for q in queries]
                    hits = fuse_by_parent_id(all_hits)
                else:
                    hits = self.retrieve(question, top_k=top_k)
            except Exception as e:
                print(f"[warn] query rewrite failed, falling back: {e}")
                hits = self.retrieve(question, top_k=top_k)
        else:
            hits = self.retrieve(question, top_k=top_k)

        if not hits:
            return {
                "answer": "知识库为空。请先运行 `python src/indexer.py` 索引文档。",
                "sources": [],
                "confidence": 0.0,
            }

        max_conf = max((h.get("confidence", 0) for h in hits), default=0)
        if max_conf < CONFIDENCE_THRESHOLD:
            return {
                "answer": f"资料中未找到与该问题相关的内容（最高置信度 {max_conf:.2f}）。建议换个说法或检查文档是否已索引。",
                "sources": self._enrich_sources(hits[:2]),
                "confidence": max_conf,
            }

        context = self.retriever.format_for_llm(hits)
        history_text = format_history(history)

        # 注入用户记忆（可选，config.ENABLE_MEMORY=True 时启用）
        memory_text = ""
        if getattr(config, "ENABLE_MEMORY", False):
            try:
                from memory import build_memory_context
                memory_text = build_memory_context(question)
                if memory_text:
                    print(f"[info] 已注入 {len(memory_text)} 字符记忆上下文")
            except Exception as e:
                print(f"[warn] memory 加载失败，跳过: {e}")

        # Build chat messages: system + (optional) history + current
        msgs = [SystemMessage(content=STRICT_SYSTEM_PROMPT)]
        # Add prior conversation (excluding the current question)
        for m in history[:-1] if history else []:
            if m["role"] == "user":
                msgs.append(HumanMessage(content=m["content"]))
            else:
                msgs.append(AIMessage(content=m["content"]))
        # Current question with context
        if memory_text:
            context = memory_text + "\n\n" + context
        current = USER_TEMPLATE.format(
            context=context, history=history_text, question=question
        )
        msgs.append(HumanMessage(content=current))

        response = self.llm.invoke(msgs)
        answer = response.content if hasattr(response, "content") else str(response)

        return {
            "answer": answer,
            "sources": self._enrich_sources(hits),
            "confidence": max_conf,
        }

    def _enrich_sources(self, hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add file path, line context, and outline heading to each source."""
        enriched = []
        for i, h in enumerate(hits, 1):
            meta = h.get("metadata", {})
            src = meta.get("source", "unknown")
            file_path = PROJECT_ROOT / src
            line_ctx = meta.get("start_line", 0)
            heading = None
            context_snippet = ""
            if file_path.exists() and file_path.suffix == ".md":
                try:
                    from outline import extract_outline
                    outline = extract_outline(file_path)
                    if line_ctx:
                        heading = find_heading_at_line(outline, line_ctx)
                    context_snippet = snippet_with_context(file_path, line_ctx or 1, context=2)
                except Exception:
                    pass
            enriched.append({
                "index": i,
                "source": src,
                "confidence": h.get("confidence", 0),
                "snippet": h.get("content", "")[:300],
                "heading": heading["title"] if heading else None,
                "line": line_ctx,
                "context": context_snippet,
            })
        return enriched