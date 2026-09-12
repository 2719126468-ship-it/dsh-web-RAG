"""Streamlit chat UI for the upgraded RAG system."""
import streamlit as st
from pathlib import Path

from pathlib import Path
from qa import RAGEngine, CONFIDENCE_THRESHOLD
from outline import build_outline_tree, find_heading_at_line, snippet_with_context

st.set_page_config(page_title="私人知识库问答 Pro", page_icon="📚", layout="wide")

st.title("📚 私人知识库问答 Pro")
st.caption("BM25 + 向量 + Rerank · 增量索引 · 引用高亮跳转")


def render_outline_sidebar():
    """Render document outline tree in the sidebar."""
    tree = build_outline_tree()
    st.sidebar.header("📂 文档目录")
    total_files = len(tree)
    total_size = sum(t["size"] for t in tree)
    st.sidebar.metric("文档数", total_files)
    st.sidebar.metric("总大小", f"{total_size/1024:.1f} KB")
    st.sidebar.divider()
    for entry in tree:
        with st.sidebar.expander(f"📄 {entry['file']} ({entry['size']/1024:.1f}KB)"):
            if not entry["outline"]:
                st.caption("(无标题)")
                continue
            for h in entry["outline"]:
                indent = "  " * (h["level"] - 1)
                st.markdown(f"{indent}- {h['title']} _(L{h['line']})_")
            st.caption(f"路径: `{entry['path']}`")


@st.cache_resource(show_spinner="正在加载模型与向量库...")
def get_engine():
    return RAGEngine(use_rerank=True)


try:
    engine = get_engine()
except Exception as e:
    st.error(f"初始化失败: {e}")
    st.info("提示：请先运行 `python src/indexer.py` 索引文档，并在 .env 中填好 DEEPSEEK_API_KEY。")
    st.stop()

render_outline_sidebar()

# Sidebar settings
with st.sidebar:
    st.divider()
    st.header("⚙️ 设置")
    top_k = st.slider("Top-K", 1, 10, 5)
    show_sources = st.checkbox("显示引用来源", value=True)
    show_context = st.checkbox("显示原文上下文", value=True)
    st.divider()
    if st.button("🗑️ 清空对话"):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources") and show_sources:
            for s in msg["sources"]:
                with st.expander(f"📎 [{s['index']}] {Path(s['source']).name} (置信度 {s['confidence']:.2f})"):
                    if s.get("heading"):
                        st.markdown(f"**章节：** {s['heading']}")
                    st.caption(f"来源：`{s['source']}`")
                    st.markdown("**引用片段：**")
                    st.info(s["snippet"])
                    if show_context and s.get("context"):
                        st.markdown("**原文上下文：**")
                        st.code(s["context"], language="markdown")

if prompt := st.chat_input("向你的私人知识库提问..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("混合检索 + rerank + 生成中..."):
            try:
                result = engine.query(
                    prompt,
                    history=st.session_state.messages,
                    top_k=top_k,
                )
            except Exception as e:
                st.error(f"调用失败: {e}")
                st.stop()
        conf = result.get("confidence", 0)
        if conf < CONFIDENCE_THRESHOLD:
            st.warning(f"⚠️ 置信度较低 ({conf:.2f})")
        st.markdown(result["answer"])
        if result["sources"] and show_sources:
            for s in result["sources"]:
                with st.expander(f"📎 [{s['index']}] {Path(s['source']).name} (置信度 {s['confidence']:.2f})"):
                    if s.get("heading"):
                        st.markdown(f"**章节：** {s['heading']}")
                    st.caption(f"来源：`{s['source']}`")
                    st.markdown("**引用片段：**")
                    st.info(s["snippet"])
                    if show_context and s.get("context"):
                        st.markdown("**原文上下文：**")
                        st.code(s["context"], language="markdown")
    st.session_state.messages.append({
        "role": "assistant",
        "content": result["answer"],
        "sources": result["sources"],
        "confidence": result.get("confidence", 0),
    })