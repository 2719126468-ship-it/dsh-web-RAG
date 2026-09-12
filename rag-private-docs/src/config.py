"""Centralized config loader for the RAG project."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Config:
    # ========== DeepSeek ==========
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    # ========== Embeddings ==========
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "512"))

    # ========== Qdrant ==========
    QDRANT_PATH: str = os.getenv("QDRANT_PATH", "./qdrant_data")
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "private_docs")
    QDRANT_MODE: str = os.getenv("QDRANT_MODE", "local")
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")

    # ========== Chunking ==========
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 80

    # ========== Retrieval ==========
    TOP_K: int = 5

    # ========== PDF 解析器 ==========
    PDF_PARSER: str = "default"

    # ========== 多模态（可选）==========
    ENABLE_MULTIMODAL: bool = False
    VLM_MODEL: str = "gpt-4o-mini"
    VLM_BASE_URL: str = ""
    VLM_API_KEY: str = ""

    # ========== 对话记忆（可选）==========
    ENABLE_MEMORY: bool = False
    MEMORY_PATH: str = "../memory/memories.json"
    MEMORY_TOP_K: int = 3

    # ========== API / Webhook（可选）==========
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    WEBHOOK_URL: str = ""


config = Config()
