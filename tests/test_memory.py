"""memory.py 单元测试：分词、增删、检索、多用户隔离。

每个测试用独立临时目录，不影响真实 memories.json。
不依赖 langchain，Termux 和 CI 都能跑。
"""
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "rag-private-docs" / "src"
sys.path.insert(0, str(SRC))

pytest.importorskip("dotenv", reason="需要 python-dotenv")


@pytest.fixture
def isolated_memory(tmp_path, monkeypatch):
    from config import config
    monkeypatch.setattr(config, "MEMORY_PATH", str(tmp_path / "memories.json"))
    yield tmp_path


def test_tokenize_chinese():
    from memory import _tokenize
    tokens = _tokenize("合同金额")
    assert "合同" in tokens
    assert "金额" in tokens


def test_tokenize_english():
    from memory import _tokenize
    tokens = _tokenize("hello world")
    assert "hello" in tokens
    assert "world" in tokens


def test_tokenize_mixed():
    from memory import _tokenize
    tokens = _tokenize("Python 编程")
    assert "python" in tokens
    assert "编程" in tokens


def test_add_and_list(isolated_memory):
    from memory import add_memory, list_memories
    add_memory("用户偏好中文")
    add_memory("公司地址在上海")
    items = list_memories()
    assert len(items) == 2
    contents = [m["content"] for m in items]
    assert "用户偏好中文" in contents
    assert "公司地址在上海" in contents


def test_search_hit(isolated_memory):
    from memory import add_memory, search_memory
    add_memory("用户偏好中文回答")
    add_memory("公司地址在上海浦东")
    results = search_memory("偏好")
    assert len(results) >= 1
    assert any("偏好" in r["content"] for r in results)


def test_search_miss(isolated_memory):
    from memory import add_memory, search_memory
    add_memory("用户偏好中文")
    results = search_memory("完全无关的查询xyzabc")
    assert results == []


def test_delete(isolated_memory):
    from memory import add_memory, list_memories, delete_memory
    item = add_memory("待删除")
    assert delete_memory(item["id"]) is True
    assert list_memories() == []
    assert delete_memory("不存在的id") is False


def test_user_isolation(isolated_memory):
    from memory import add_memory, list_memories
    add_memory("用户A的记忆", user_id="alice")
    add_memory("用户B的记忆", user_id="bob")
    alice = list_memories(user_id="alice")
    bob = list_memories(user_id="bob")
    assert len(alice) == 1
    assert len(bob) == 1
    assert alice[0]["content"] == "用户A的记忆"
    assert bob[0]["content"] == "用户B的记忆"


def test_build_memory_context(isolated_memory):
    from memory import add_memory, build_memory_context
    add_memory("用户偏好用中文回答")
    ctx = build_memory_context("我的语言偏好？")
    assert "中文" in ctx
    assert "历史记忆" in ctx


def test_empty_search(isolated_memory):
    from memory import search_memory
    assert search_memory("任何东西") == []
