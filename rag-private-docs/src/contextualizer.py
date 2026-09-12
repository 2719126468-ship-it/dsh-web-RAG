"""Contextual Retrieval: prepend LLM-generated context to each chunk.

Idea (from Anthropic, 2024): a chunk like "The result is 42%" is
unclear out of context. If we prepend context like "This is from the
ablation study of BERT on SST-2", retrieval quality improves by ~35%.

Process:
  1. Take the whole document
  2. For each chunk, ask the LLM to write a 50-100 char context line
     that situates the chunk in the document
  3. Prepend the context to the chunk text before embedding

Cost: ~$0.001 per chunk with DeepSeek. For 1000 chunks, ~$1.
"""
import os
import time
from pathlib import Path
from collections import defaultdict
from typing import List

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate


CONTEXT_PROMPT = '''请根据文档全文，为下面这段文字写一段 50-100 字的"上下文说明"，让读者无需看完整文档就能理解这段在讲什么。

要求：
1. 只用中文
2. 说明这段属于哪个章节、讨论什么主题
3. 不要复述这段内容本身
4. 用一段连贯的话，不要分点

【文档标题】
{title}

【待标注段落】
{chunk}

【上下文说明】
'''

BATCH_CONTEXT_PROMPT = '''请为以下文档中的多个段落分别写 50-100 字的上下文说明。

【文档标题】
{title}

{chunks}

请按顺序输出，每段用 "--- 第N段 ---" 分隔（N 从 1 开始）。
只输出说明文字，不要复述段落内容，不要加标题或编号以外的文字。
'''

def _sep(n: int) -> str:
    return f"--- 第{n}段 ---"


class Contextualizer:
    """Adds LLM-generated context to each chunk."""

    def __init__(self, batch_size: int = 5, model: str = None):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not set in .env")
        self.llm = ChatOpenAI(
            model=model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            temperature=0.0,
        )
        self.batch_size = batch_size
        self.prompt_single = ChatPromptTemplate.from_template(CONTEXT_PROMPT)
        self.prompt_batch = ChatPromptTemplate.from_template(BATCH_CONTEXT_PROMPT)

    def _infer_title(self, docs: List[Document]) -> str:
        if not docs:
            return "Unknown document"
        first = docs[0].page_content[:500]
        for line in first.split("\n"):
            s = line.strip()
            if s.startswith("# "):
                return s[2:].strip()
            if s and not s.startswith("#"):
                return s[:80]
        return "Unknown document"

    def _batch_contexts(self, title: str, chunks: List[str]) -> List[str]:
        """Ask LLM for N context strings in a single call."""
        numbered = "\n\n".join(
            f"[段落 {i+1}]\n{c[:600]}" for i, c in enumerate(chunks)
        )
        prompt = self.prompt_batch.format(title=title, chunks=numbered)
        try:
            resp = self.llm.invoke(prompt)
            text = resp.content if hasattr(resp, "content") else str(resp)
        except Exception as e:
            print(f"[warn] LLM batch context failed: {e}; falling back to per-chunk")
            return [self._single_context(title, c) for c in chunks]

        # Parse output by separators
        contexts = [""] * len(chunks)
        for i in range(len(chunks)):
            sep = _sep(i + 1)
            if sep in text:
                idx = text.index(sep) + len(sep)
                end_idx = len(text)
                for j in range(i + 2, len(chunks) + 2):
                    next_sep = _sep(j)
                    if next_sep in text[idx:]:
                        end_idx = text.index(next_sep, idx)
                        break
                contexts[i] = text[idx:end_idx].strip()
        contexts = [c if c else "[无上下文]" for c in contexts]
        return contexts

    def _single_context(self, title: str, chunk: str) -> str:
        try:
            prompt = self.prompt_single.format(title=title, chunk=chunk[:1500])
            resp = self.llm.invoke(prompt)
            return (resp.content if hasattr(resp, "content") else str(resp)).strip()
        except Exception:
            return ""

    def contextualize(self, docs: List[Document]) -> List[Document]:
        if not docs:
            return []
        title = self._infer_title(docs)
        groups = defaultdict(list)
        for i, d in enumerate(docs):
            groups[d.metadata.get("source", "unknown")].append((i, d))

        new_docs = [None] * len(docs)
        total_batches = sum((len(v) + self.batch_size - 1) // self.batch_size for v in groups.values())
        batch_idx = 0
        for src, items in groups.items():
            for start in range(0, len(items), self.batch_size):
                batch = items[start:start + self.batch_size]
                chunks = [d.page_content for _, d in batch]
                batch_idx += 1
                print(f"[ctx] batch {batch_idx}/{total_batches} ({len(batch)} chunks from {Path(src).name})")
                contexts = self._batch_contexts(title, chunks)
                for (orig_idx, d), ctx in zip(batch, contexts):
                    new_text = f"【{ctx}】\n\n{d.page_content}"
                    new_meta = dict(d.metadata)
                    new_meta["context"] = ctx
                    new_docs[orig_idx] = Document(page_content=new_text, metadata=new_meta)
                time.sleep(0.2)
        return new_docs


if __name__ == "__main__":
    print("Contextualizer is meant to be called from indexer.py.")