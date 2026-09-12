"""第 1 课：直接调用 LLM（不经过 RAG）

目标：
  - 理解 LLM 是怎么调用的
  - 看到 LLM 的"幻觉"问题（不知道的事情会瞎编）
  - 体验"温度"参数对输出的影响

运行：
  python example_lessons/01_hello_llm.py
"""
import os
import sys
from pathlib import Path

# Load .env
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate


def get_llm(temperature: float = 0.7) -> ChatOpenAI:
    """Create an LLM client using the OpenAI-compatible DeepSeek API."""
    return ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        temperature=temperature,
    )


def demo_basic_chat():
    """Lesson 1.1: A single round-trip chat."""
    print("=" * 60)
    print("1.1 基础对话")
    print("=" * 60)
    llm = get_llm()
    response = llm.invoke("用一句话解释什么是 RAG？")
    print(f"\nQ: 用一句话解释什么是 RAG？\nA: {response.content}\n")


def demo_temperature():
    """Lesson 1.2: Temperature controls randomness."""
    print("=" * 60)
    print("1.2 温度参数（temperature）")
    print("=" * 60)
    print("temperature 越低 → 越确定、越保守")
    print("temperature 越高 → 越随机、越有创造性")
    print()
    for t in [0.0, 0.5, 1.0]:
        llm = get_llm(temperature=t)
        resp = llm.invoke("给我的私人知识库起一个产品名字，要求两个字，中文")
        print(f"  temperature={t}: {resp.content}")


def demo_hallucination():
    """Lesson 1.3: Watch the LLM make things up."""
    print("=" * 60)
    print("1.3 幻觉演示（这是 RAG 要解决的问题）")
    print("=" * 60)
    llm = get_llm()
    # Ask about a fictional person/contract
    resp = llm.invoke("蓝海科技 2024 年签订的智能客服系统合同金额是多少？")
    print(f"\nQ: 蓝海科技 2024 年签订的智能客服系统合同金额是多少？")
    print(f"A: {resp.content}")
    print()
    print("⚠️  注意：如果你的知识库里没有这份合同，LLM 会瞎编一个数字。")
    print("    这就是为什么我们需要 RAG —— 让 LLM 只能基于真实文档回答。")


def main():
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("[error] DEEPSEEK_API_KEY not set. Edit .env first.")
        return
    demo_basic_chat()
    print()
    demo_temperature()
    print()
    demo_hallucination()


if __name__ == "__main__":
    main()
