"""config.py 字段完整性测试。

确保所有新增配置项都在 Config 类里，可以被 config.XXX 访问。
"""
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "rag-private-docs" / "src"
sys.path.insert(0, str(SRC))

pytest.importorskip("dotenv", reason="需要 python-dotenv")


REQUIRED_FIELDS = [
    "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL",
    "EMBEDDING_MODEL", "EMBEDDING_DIM",
    "QDRANT_PATH", "COLLECTION_NAME",
    "CHUNK_SIZE", "CHUNK_OVERLAP", "TOP_K",
    "QDRANT_MODE", "QDRANT_URL", "QDRANT_API_KEY",
    "PDF_PARSER",
    "ENABLE_MULTIMODAL", "VLM_MODEL", "VLM_BASE_URL", "VLM_API_KEY",
    "ENABLE_MEMORY", "MEMORY_PATH", "MEMORY_TOP_K",
    "API_HOST", "API_PORT", "WEBHOOK_URL",
]


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_config_field_exists(field):
    from config import config
    assert hasattr(config, field), f"config 缺少字段：{field}"


def test_embedding_dim_is_positive():
    from config import config
    assert config.EMBEDDING_DIM > 0


def test_chunk_overlap_less_than_size():
    from config import config
    assert config.CHUNK_OVERLAP < config.CHUNK_SIZE
