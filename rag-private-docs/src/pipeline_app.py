"""独立的流水线可视化入口。

运行：cd rag-private-docs/src && streamlit run pipeline_app.py
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))

import streamlit as st  # noqa: E402

from pipeline_ui import render_pipeline  # noqa: E402

st.set_page_config(page_title="RAG 流水线", layout="wide")
st.title("RAG 流水线可视化")
render_pipeline()
