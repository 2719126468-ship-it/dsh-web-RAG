"""DeepDoc PDF 解析器（可选）。

依赖 deepdoc_pdfparser（从 RAGFlow 抽出的独立包）。
未安装时返回空列表，调用方会 fallback 到默认解析器。
"""
from pathlib import Path
from typing import List

from langchain_core.documents import Document


def is_available() -> bool:
    try:
        import deepdoc_pdfparser  # noqa: F401
        return True
    except ImportError:
        return False


def parse_pdf_deepdoc(path: Path) -> List[Document]:
    """用 DeepDoc 解析 PDF，返回 Document 列表。"""
    if not is_available():
        print(f"[warn] deepdoc_pdfparser 未安装，跳过 {path.name}")
        return []

    try:
        from deepdoc_pdfparser import RAGFlowPdfParser
    except ImportError as e:
        print(f"[warn] 导入 RAGFlowPdfParser 失败：{e}")
        return []

    try:
        parser = RAGFlowPdfParser()
        sections = parser.parse(str(path))
    except Exception as e:
        print(f"[warn] DeepDoc 解析失败 {path}: {e}")
        return []

    docs = []
    for sec in sections:
        text = getattr(sec, "text", None) or str(sec)
        if not text.strip():
            continue
        docs.append(Document(
            page_content=text,
            metadata={
                "source": str(path),
                "page": getattr(sec, "page", None),
                "parser": "deepdoc",
            },
        ))
    return docs
