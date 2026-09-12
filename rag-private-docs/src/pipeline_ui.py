"""轻量级 RAG 流水线可视化面板。

作为独立页面，不改动现有 app.py。
单独运行：streamlit run src/pipeline_app.py
"""
import streamlit as st

from config import config


def render_pipeline():
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["数据源", "解析", "分块", "索引", "检索"]
    )

    with tab1:
        st.subheader("数据源")
        uploaded = st.file_uploader("上传文档（可多选）", accept_multiple_files=True)
        if uploaded:
            st.success(f"已选择 {len(uploaded)} 个文件")
            if st.button("保存到 docs/"):
                from pathlib import Path
                docs_dir = Path(__file__).resolve().parent.parent / "docs"
                docs_dir.mkdir(parents=True, exist_ok=True)
                for f in uploaded:
                    (docs_dir / f.name).write_bytes(f.read())
                st.success("已保存，请到『索引』页签重建")

    with tab2:
        st.subheader("解析器配置")
        current = getattr(config, "PDF_PARSER", "default")
        parser = st.selectbox(
            "PDF 解析器", ["default", "deepdoc"],
            index=0 if current == "default" else 1,
        )
        st.info(f"当前配置：{parser}（改 config.py 后需重启生效）")
        st.caption("deepdoc 需要先安装 deepdoc-pdfparser，未装则自动 fallback 到默认")

    with tab3:
        st.subheader("分块策略")
        chunk_size = st.slider("CHUNK_SIZE", 200, 1500, config.CHUNK_SIZE)
        overlap = st.slider("CHUNK_OVERLAP", 0, 300, config.CHUNK_OVERLAP)
        st.caption(f"当前：size={chunk_size}, overlap={overlap}")
        st.caption("调参后需重新索引才生效")

    with tab4:
        st.subheader("索引管理")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("增量索引"):
                with st.spinner("索引中..."):
                    import indexer
                    result = indexer.main(force=False)
                st.success(f"完成：{result}")
        with col2:
            confirm = st.checkbox("确认清空现有索引")
            if st.button("全量重建") and confirm:
                with st.spinner("重建中..."):
                    import indexer
                    result = indexer.main(force=True)
                st.success(f"完成：{result}")

    with tab5:
        st.subheader("检索测试")
        q = st.text_input("输入查询")
        top_k = st.slider("TOP_K", 1, 20, config.TOP_K)
        if q:
            st.info("检索接口请根据 retriever.py 的实际函数名调整下方代码")
            st.code(
                "from retriever import retrieve\n"
                "results = retrieve(q, top_k=top_k)",
                language="python",
            )
            st.caption(f"当前查询：{q}，TOP_K={top_k}")
