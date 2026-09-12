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

# ========== Qdrant 部署模式 ==========
# "local"：嵌入式本地模式（默认，数据存 qdrant_data/）
# "server"：连接远程 Qdrant 服务（如 Docker 部署的 qdrant/qdrant）
QDRANT_MODE = "local"
QDRANT_URL = "http://localhost:6333"
QDRANT_API_KEY = ""

# PDF 解析器选择：default 用现有解析器，deepdoc 用 DeepDoc（需额外安装）
PDF_PARSER = "default"

# ========== 多模态（可选）==========
# 开启后会从 PDF 提取图片，用 VLM 生成描述，参与检索
ENABLE_MULTIMODAL = False
VLM_MODEL = "gpt-4o-mini"
VLM_BASE_URL = ""
VLM_API_KEY = ""

# ========== 对话记忆（可选）==========
ENABLE_MEMORY = False
MEMORY_PATH = "../memory/memories.json"
MEMORY_TOP_K = 3

# ========== API / Webhook（可选）==========
API_HOST = "0.0.0.0"
API_PORT = 8000
WEBHOOK_URL = ""
