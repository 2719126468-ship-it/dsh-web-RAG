"""老式 .doc 解析器（优雅降级版）。

纯 Python 没有可靠解析 .doc 的库。这里优先尝试 unstructured，
没有则给出明确提示，建议先转成 .docx。
"""
from pathlib import Path
from typing import List

from langchain_core.documents import Document


def parse_doc(path: Path) -> List[Document]:
    try:
        from unstructured.partition.doc import partition_doc
    except ImportError:
        print(
            f"[warn] 无法解析老式 .doc：{path.name}\n"
            f"       建议先转成 .docx，或安装：pip install unstructured"
        )
        return []

    try:
        elements = partition_doc(filename=str(path))
    except Exception as e:
        print(f"[warn] 解析 .doc 失败 {path}: {e}")
        return []

    text = "\n".join(str(el) for el in elements if str(el).strip())
    if not text:
        return []
    return [Document(page_content=text, metadata={"source": str(path)})]
