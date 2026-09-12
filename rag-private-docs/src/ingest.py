# 【旧版脚本，已不推荐使用】日常请用 indexer.py（支持增量索引、更多格式）。
# 本脚本是早期全量重建实现，保留仅作参考。
"""Document ingestion pipeline.

Reads files from ./docs, splits into chunks, embeds, and stores in local Qdrant.
Supported: .md, .txt, .pdf, .docx
"""
import sys
from pathlib import Path

from langchain_community.document_loaders import (
    DirectoryLoader,
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from config import config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"


def build_loader():
    """Build a loader that handles multiple file types in ./docs."""
    return [
        DirectoryLoader(
            str(DOCS_DIR), glob="**/*.md", loader_cls=TextLoader,
            recursive=True, show_progress=True,
            loader_kwargs={"encoding": "utf-8"},
        ),
        DirectoryLoader(
            str(DOCS_DIR), glob="**/*.txt", loader_cls=TextLoader,
            recursive=True, show_progress=True,
            loader_kwargs={"encoding": "utf-8"},
        ),
        DirectoryLoader(
            str(DOCS_DIR), glob="**/*.pdf", loader_cls=PyPDFLoader,
            recursive=True, show_progress=True,
        ),
        DirectoryLoader(
            str(DOCS_DIR), glob="**/*.docx", loader_cls=Docx2txtLoader,
            recursive=True, show_progress=True,
        ),
    ]


def load_documents():
    docs = []
    for loader in build_loader():
        try:
            docs.extend(loader.load())
        except Exception as e:
            print(f"[warn] Loader skipped: {e}")
    print(f"[info] Loaded {len(docs)} raw documents")
    return docs


def split_documents(docs):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "！", "？", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    print(f"[info] Split into {len(chunks)} chunks")
    return chunks


def build_embeddings():
    print(f"[info] Loading embedding model: {config.EMBEDDING_MODEL}")
    return HuggingFaceEmbeddings(
        model_name=config.EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def ingest():
    if not DOCS_DIR.exists() or not any(DOCS_DIR.iterdir()):
        print(f"[error] No documents found in {DOCS_DIR}. Add some .md/.txt/.pdf files first.")
        sys.exit(1)

    docs = load_documents()
    if not docs:
        print("[error] No documents could be loaded.")
        sys.exit(1)

    chunks = split_documents(docs)
    embeddings = build_embeddings()

    qdrant_path = PROJECT_ROOT / config.QDRANT_PATH.lstrip("./")
    qdrant_path.mkdir(parents=True, exist_ok=True)

    print(f"[info] Ingesting into Qdrant at {qdrant_path} (collection={config.COLLECTION_NAME})")
    QdrantVectorStore.from_documents(
        chunks,
        embeddings,
        path=str(qdrant_path),
        collection_name=config.COLLECTION_NAME,
        force_recreate=True,
    )
    print(f"[done] Ingested {len(chunks)} chunks. Run: streamlit run src/app.py")


if __name__ == "__main__":
    ingest()