"""Qdrant client 工厂：根据 config.QDRANT_MODE 创建本地或远程客户端。"""
from pathlib import Path

from qdrant_client import QdrantClient

from config import config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
def _resolve_qdrant_path(raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (PROJECT_ROOT / p).resolve()


QDRANT_PATH = _resolve_qdrant_path(config.QDRANT_PATH)


def create_qdrant_client() -> QdrantClient:
    """根据 config.QDRANT_MODE 创建 Qdrant 客户端。

    - local:  嵌入式本地模式，数据存 qdrant_data/ 目录
    - server: 连接远程 Qdrant 服务
    """
    mode = getattr(config, "QDRANT_MODE", "local").lower()

    if mode == "server":
        url = getattr(config, "QDRANT_URL", "http://localhost:6333")
        api_key = getattr(config, "QDRANT_API_KEY", "") or None
        kwargs = {"url": url}
        if api_key:
            kwargs["api_key"] = api_key
        print(f"[info] 连接远程 Qdrant: {url}")
        return QdrantClient(**kwargs)

    QDRANT_PATH.mkdir(parents=True, exist_ok=True)
    print(f"[info] 使用本地 Qdrant: {QDRANT_PATH}")
    return QdrantClient(path=str(QDRANT_PATH))
