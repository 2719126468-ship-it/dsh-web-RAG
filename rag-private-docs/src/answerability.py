"""Evidence-based answerability gate for RAG.

The verifier is intentionally separate from retrieval confidence:
retrieval asks "is this passage related?", while this gate asks
"does the supplied context contain the specific answer the question asks for?"

It uses one LLM call only when the retrieval stage has returned candidates.
For an ANSWERABLE verdict, the model must also provide a verbatim evidence
span that is present in the supplied context. This makes the gate auditable
and prevents a free-form "yes" from being trusted on its own.

Environment:
  USE_ANSWERABILITY_CHECK=true|false   (default: true)
"""

import json
import os
import re
from typing import Any, Dict, List, Optional


ANSWERABILITY_PROMPT = """你是私人知识库的“证据可回答性检查器”。

你的任务不是判断“问题和资料是否相关”，而是判断：
**参考资料中是否明确包含了当前问题所要求的具体答案。**

严格规则：
1. 只能依据【参考资料】判断，不得使用常识、训练数据或推测。
2. “主题相关但没有答案”必须判为 UNANSWERABLE。
3. 只有当参考资料明确写出了问题要求的事实、数值、日期、人物、地点、条件、列表等，才能判为 ANSWERABLE。
4. 如果问题问“多少/几天/什么时候/是谁/哪些/是否”等，必须在资料中找到对应的具体答案，不能因为出现同一主题词就判为 ANSWERABLE。
5. 判为 ANSWERABLE 时，必须给出一段**逐字摘自参考资料**的 evidence；evidence 必须是原文连续子串，不能改写。
6. 判为 UNANSWERABLE 时，evidence 必须为空字符串。
7. 只输出一个 JSON 对象，不要输出 Markdown、解释或其他文字。

输出格式：
{"verdict":"ANSWERABLE","evidence":"参考资料中的逐字原文"}
或
{"verdict":"UNANSWERABLE","evidence":""}

【当前问题】
{question}

【参考资料】
{context}
"""


class AnswerabilityChecker:
    """Verify whether retrieved context contains a specific answer."""

    def __init__(self):
        enabled = os.getenv("USE_ANSWERABILITY_CHECK", "true").lower() == "true"
        self.enabled = enabled
        self.llm = None
        self.prompt = None

        if not enabled:
            return

        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key or api_key.startswith("sk-xxxxxxx"):
            return

        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI

        self.prompt = ChatPromptTemplate.from_template(ANSWERABILITY_PROMPT)
        self.llm = ChatOpenAI(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            temperature=0.0,
        )

    @staticmethod
    def _context_text(hits: List[Dict[str, Any]], max_total_chars: int = 12000) -> str:
        """Build a compact, source-labelled context for verification."""
        blocks: List[str] = []
        total = 0

        seen_parents = set()

        for hit in hits:
            meta = hit.get("metadata", {})
            source = meta.get("source", "unknown")
            parent_id = meta.get("parent_id")
            parent_text = meta.get("parent_text", "")

            # Match the presentation contract used by retriever.format_for_llm:
            # show each parent once, otherwise use the hit content.
            if parent_text and parent_id:
                if parent_id in seen_parents:
                    continue
                seen_parents.add(parent_id)
                content = parent_text
            else:
                content = hit.get("content", "")

            content = str(content).strip()
            if not content:
                continue

            # Keep each individual block bounded so one giant document cannot
            # crowd out all other evidence.
            content = content[:3500]
            block = f"[{len(blocks) + 1}] {source}\n{content}"
            if total + len(block) > max_total_chars:
                remaining = max_total_chars - total
                if remaining < 200:
                    break
                block = block[:remaining]

            blocks.append(block)
            total += len(block)

        return "\n\n".join(blocks)

    @staticmethod
    def _parse_response(text: str) -> Optional[Dict[str, str]]:
        """Parse the strict JSON response, tolerating a fenced JSON block."""
        text = (text or "").strip()
        if not text:
            return None

        fenced = re.search(r"\{.*\}", text, flags=re.DOTALL)
        candidate = fenced.group(0) if fenced else text

        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            return None

        verdict = str(data.get("verdict", "")).strip().upper()
        evidence = str(data.get("evidence", ""))

        if verdict not in {"ANSWERABLE", "UNANSWERABLE"}:
            return None
        return {"verdict": verdict, "evidence": evidence}

    @classmethod
    def _validate_answerable(
        cls, parsed: Dict[str, str], context: str
    ) -> bool:
        """Require exact evidence grounding for ANSWERABLE."""
        if parsed.get("verdict") != "ANSWERABLE":
            return False

        evidence = parsed.get("evidence", "").strip()
        if len(evidence) < 4:
            return False

        # The evidence must literally occur in the context we supplied.
        return evidence in context

    def check(self, question: str, hits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Return a grounded verdict.

        status:
          ANSWERABLE       -> explicit answer evidence found
          UNANSWERABLE     -> verifier says the answer is absent
          SKIPPED          -> gate disabled/unavailable/invalid response
          ERROR            -> verifier call failed
        """
        if not hits:
            return {"status": "UNANSWERABLE", "evidence": "", "reason": "no_hits"}

        if not self.enabled or self.llm is None:
            return {
                "status": "SKIPPED",
                "evidence": "",
                "reason": "llm_unavailable_or_disabled",
            }

        context = self._context_text(hits)
        if not context:
            return {"status": "UNANSWERABLE", "evidence": "", "reason": "empty_context"}

        try:
            response = self.llm.invoke(
                self.prompt.format(question=question, context=context)
            )
            raw = response.content if hasattr(response, "content") else str(response)
            parsed = self._parse_response(str(raw))
        except Exception as exc:
            print(f"[warn] answerability check failed: {exc}; continuing")
            return {"status": "ERROR", "evidence": "", "reason": "llm_error"}

        if parsed is None:
            print("[warn] answerability checker returned invalid JSON; continuing")
            return {"status": "SKIPPED", "evidence": "", "reason": "invalid_response"}

        if parsed["verdict"] == "UNANSWERABLE":
            return {
                "status": "UNANSWERABLE",
                "evidence": "",
                "reason": "verifier",
            }

        if self._validate_answerable(parsed, context):
            return {
                "status": "ANSWERABLE",
                "evidence": parsed["evidence"].strip(),
                "reason": "grounded_evidence",
            }

        print("[warn] answerability checker said ANSWERABLE without grounded evidence; continuing")
        return {
            "status": "SKIPPED",
            "evidence": "",
            "reason": "ungrounded_evidence",
        }
