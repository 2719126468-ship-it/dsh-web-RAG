#!/bin/sh
# 一键安装：创建 venv、装依赖、准备 .env
set -e

echo "=== DSH Web RAG 安装脚本 ==="
echo

# 1. 检查 Python
if ! command -v python3 >/dev/null 2>&1; then
    echo "[错误] 未找到 python3，请先安装 Python 3.11+"
    exit 1
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[info] Python 版本：$PY_VER"

# 2. 创建 venv
cd rag-private-docs
if [ -d ".venv" ]; then
    echo "[info] .venv 已存在，跳过创建"
else
    echo "[info] 创建虚拟环境..."
    python3 -m venv .venv
fi

# 3. 装依赖
echo "[info] 安装依赖..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
.venv/bin/pip install pytest -q

# 4. 准备 .env
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "[info] 从 .env.example 创建 .env"
    cp .env.example .env
    echo "[重要] 请编辑 rag-private-docs/.env 填入 DEEPSEEK_API_KEY"
fi

echo
echo "=== 安装完成 ==="
echo "接下来："
echo "  cd rag-private-docs/src"
echo "  python indexer.py --force     # 首次索引"
echo "  streamlit run app.py          # 启动 Web 界面"
