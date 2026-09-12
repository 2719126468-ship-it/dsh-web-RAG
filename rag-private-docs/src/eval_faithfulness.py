"""Faithfulness 评估：判断答案是否严格基于检索到的上下文。

用法：
    python eval_faithfulness.py path/to/qa_results.json

输入 JSON 格式：
    [
      {"question": "...", "answer": "...", "contexts": ["...", "..."]},
      ...
    ]
"""
import json
import os
import sys
from typing import Dict, List


def evaluate_faithfulness(question: str, answer: str, contexts: List[str]) -> Dict:
    """调用 DeepSeek API 评估答案对上下文的忠实度。

    返回：
        {
            "score": 0.0-1.0,
            "claims": [{"text": ..., "supported": bool, "evidence": ...}, ...],
            "unsupported": ["不支持的断言原文", ...]
        }
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("需要 openai 库：pip install openai")

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY")

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    client = OpenAI(api_key=api_key, base_url=base_url)
    ctx_text = "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(contexts))

    prompt = f"""你是严格的评估者。请判断「答案」中每个事实是否都能从「参考资料」中找到直接依据。

参考资料：
{ctx_text}

问题：{question}

答案：{answer}

请只输出 JSON（不要 markdown 代码块），格式：
{{
  "claims": [
    {{"text": "答案中的某条事实", "supported": true, "evidence": "引用原文"}}
  ],
  "score": 被支持 claim 占比（0.0-1.0）
}}
"""

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )

    content = resp.choices[0].message.content.strip()
    if content.startswith("```"):
        lines = content.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)
        if content.startswith("json"):
            content = content[4:].lstrip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {"score": 0.0, "claims": [], "error": "无法解析 LLM 输出", "raw": content[:500]}

    claims = data.get("claims", [])
    data["unsupported"] = [c["text"] for c in claims if not c.get("supported", False)]
    if "score" not in data and claims:
        supported = sum(1 for c in claims if c.get("supported", False))
        data["score"] = supported / len(claims) if claims else 0.0
    return data


def evaluate_batch(items: List[Dict]) -> Dict:
    results = []
    total_score = 0.0
    n = 0
    for i, item in enumerate(items, 1):
        q = item.get("question", "")
        a = item.get("answer", "")
        ctxs = item.get("contexts", [])
        print(f"[{i}/{len(items)}] {q[:50]}...")
        try:
            r = evaluate_faithfulness(q, a, ctxs)
            r["question"] = q
            results.append(r)
            total_score += r.get("score", 0.0)
            n += 1
        except Exception as e:
            print(f"  ⚠️  失败：{e}")
            results.append({"question": q, "score": 0.0, "error": str(e)})
    return {
        "average_faithfulness": round(total_score / n, 4) if n else 0.0,
        "count": n,
        "results": results,
    }


def main():
    if len(sys.argv) < 2:
        print("用法：python eval_faithfulness.py path/to/qa_results.json")
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        items = json.load(f)
    if not isinstance(items, list):
        print("❌ 输入 JSON 顶层应该是数组")
        sys.exit(1)
    summary = evaluate_batch(items)
    print()
    print("=" * 50)
    print(f"平均 Faithfulness: {summary['average_faithfulness']}")
    print(f"评估条数: {summary['count']}")
    print("=" * 50)
    for r in summary["results"]:
        q = r.get("question", "")[:40]
        s = r.get("score", 0.0)
        print(f"  {q}... score={s:.2f}")
        for u in r.get("unsupported", []):
            print(f"    ❌ 无依据: {u[:60]}")
    with open("faithfulness_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("\n详细结果已写入 faithfulness_results.json")


if __name__ == "__main__":
    main()
