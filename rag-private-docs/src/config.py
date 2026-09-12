"""Centralized config loader for the RAG project."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Config:
    # DeepSeek
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    # Embeddings
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")

    # Qdrant (local file-based, no Docker needed)
    QDRANT_PATH: str = os.getenv("QDRANT_PATH", "./qdrant_data")
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "private_docs")

    # Chunking
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 80

    # Retrieval
    TOP_K: int = 5


config = Config()

# 嵌入向量维度（与 EMBEDDING_MODEL 对应；BGE-small-zh 为 512）
EMBEDDING_DIM = 512
