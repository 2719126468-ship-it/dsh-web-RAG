"""
基础测试用例（Termux 适配版）

运行：
    cd ~/"DeepSeek RAG"
    ./rag-private-docs/.venv/bin/python -m pytest tests/ -v

依赖未安装时自动跳过，不报错。
"""

import os
import sys
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "rag-private-docs"
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))


def test_project_dir_exists():
    assert PROJECT.exists(), f"项目目录不存在：{PROJECT}"


def test_src_dir_exists():
    assert SRC.exists(), f"src 目录不存在：{SRC}"


def test_docs_directory_exists():
    docs_dir = PROJECT / "docs"
    assert docs_dir.exists(), f"docs 目录不存在：{docs_dir}"
    files = list(docs_dir.glob("*.md")) + list(docs_dir.glob("*.txt"))
    assert len(files) > 0, "docs 目录里没有 .md/.txt 文档"


def test_config_values():
    pytest.importorskip("dotenv", reason="未安装 python-dotenv")
    from config import config
    assert config.CHUNK_SIZE > 0
    assert config.CHUNK_OVERLAP >= 0
    assert config.CHUNK_OVERLAP < config.CHUNK_SIZE
    assert config.TOP_K > 0


def test_indexer_importable():
    pytest.importorskip("langchain_community", reason="未安装 langchain-community")
    import indexer
    assert hasattr(indexer, "__file__")


def test_retriever_importable():
    pytest.importorskip("langchain_huggingface", reason="未安装 langchain-huggingface")
    import retriever
    assert hasattr(retriever, "__file__")


def test_env_file_exists():
    env_file = PROJECT / ".env"
    if not env_file.exists():
        pytest.skip(".env 不存在，跳过")


def test_api_key_format():
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        pytest.skip("未设置 DEEPSEEK_API_KEY，跳过")
    assert key.startswith("sk-")


def test_eval_set_format():
    eval_file = PROJECT / "eval" / "test_set.json"
    if not eval_file.exists():
        pytest.skip("eval/test_set.json 不存在，跳过")
    with open(eval_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)
    for i, item in enumerate(data):
        assert "question" in item, f"第 {i} 项缺少 question"
        assert "ground_truth_keywords" in item, f"第 {i} 项缺少 ground_truth_keywords"
        assert isinstance(item["ground_truth_keywords"], list), f"第 {i} 项应为数组"
