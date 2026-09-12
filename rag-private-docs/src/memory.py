"""轻量对话记忆：本地 JSON 存储 + 关键词检索。

不依赖向量库和外部服务，适合个人使用。
"""
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

from config import config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = PROJECT_ROOT / "memory" / "memories.json"


def _memory_path() -> Path:
    p = getattr(config, "MEMORY_PATH", "../memory/memories.json")
    path = (PROJECT_ROOT / p.lstrip("./")).resolve() if not Path(p).is_absolute() else Path(p)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load() -> List[Dict]:
    path = _memory_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items: List[Dict]) -> None:
    _memory_path().write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _tokenize(text: str) -> List[str]:
    """中英文混合分词：中文按 2-gram，英文按空格切。"""
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    chinese = re.findall(r"[\u4e00-\u9fff]", text)
    for i in range(len(chinese) - 1):
        tokens.append(chinese[i] + chinese[i + 1])
    return tokens


def add_memory(content: str, user_id: str = "default", tags: Optional[List[str]] = None) -> Dict:
    """存储一条记忆。"""
    items = _load()
    item = {
        "id": f"mem_{int(time.time() * 1000)}",
        "user_id": user_id,
        "content": content,
        "tags": tags or [],
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    items.append(item)
    _save(items)
    return item


def search_memory(query: str, user_id: str = "default", top_k: Optional[int] = None) -> List[Dict]:
    """按关键词重叠度检索相关记忆。"""
    if top_k is None:
        top_k = getattr(config, "MEMORY_TOP_K", 3)

    items = _load()
    if not items:
        return []

    q_tokens = set(_tokenize(query))
    if not q_tokens:
        return []

    scored = []
    for item in items:
        if item.get("user_id") != user_id:
            continue
        m_tokens = set(_tokenize(item.get("content", "")))
        if not m_tokens:
            continue
        overlap = len(q_tokens & m_tokens)
        if overlap > 0:
            score = overlap / (len(q_tokens) ** 0.5)
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:top_k]]


def list_memories(user_id: str = "default") -> List[Dict]:
    return [m for m in _load() if m.get("user_id") == user_id]


def delete_memory(memory_id: str) -> bool:
    items = _load()
    new_items = [m for m in items if m.get("id") != memory_id]
    if len(new_items) == len(items):
        return False
    _save(new_items)
    return True


def build_memory_context(query: str, user_id: str = "default") -> str:
    """把检索到的记忆拼成 prompt 上下文。"""
    memories = search_memory(query, user_id=user_id)
    if not memories:
        return ""
    lines = ["以下是与当前问题相关的历史记忆："]
    for m in memories:
        lines.append(f"- {m['content']}")
    return "\n".join(lines)
