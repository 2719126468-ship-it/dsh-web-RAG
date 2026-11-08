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

    # ========== PDF parser ==========
    PDF_PARSER: str = "default"

    # ========== Multimodal (optional) ==========
    ENABLE_MULTIMODAL: bool = False
    VLM_MODEL: str = "gpt-4o-mini"
    VLM_BASE_URL: str = ""
    VLM_API_KEY: str = ""

    # ========== Conversation memory (optional) ==========
    ENABLE_MEMORY: bool = False
    MEMORY_PATH: str = "../memory/memories.json"
    MEMORY_TOP_K: int = 3

    # ========== API / Webhook ==========
    # Bind to localhost by default. Expose only behind a trusted proxy/firewall.
    API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_AUTH_TOKEN: str = os.getenv("API_AUTH_TOKEN", "")
    API_ADMIN_TOKEN: str = os.getenv("API_ADMIN_TOKEN", "")
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")


config = Config()
