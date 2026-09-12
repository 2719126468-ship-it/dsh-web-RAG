#!/bin/sh
# 项目健康检查：不需要 langchain，Termux 上也能跑
# 用法：sh diagnose.sh

echo "=== DSH Web RAG 项目自检 ==="
echo

# 1. 目录结构
echo "[1] 目录结构"
for d in rag-private-docs rag-private-docs/src rag-private-docs/docs tests .github; do
    if [ -d "$d" ]; then echo "  OK $d"; else echo "  缺失 $d"; fi
done
echo

# 2. 关键文件
echo "[2] 关键文件"
for f in README.md LICENSE .gitignore rag-private-docs/requirements.txt rag-private-docs/src/config.py rag-private-docs/src/indexer.py rag-private-docs/src/retriever.py rag-private-docs/src/qa.py; do
    if [ -f "$f" ]; then echo "  OK $f"; else echo "  缺失 $f"; fi
done
echo

# 3. Python 语法
echo "[3] Python 语法检查"
if command -v python3 >/dev/null 2>&1; then
    python3 -c "
import sys
from pathlib import Path
src = Path('rag-private-docs/src')
fail = 0
for f in sorted(src.glob('*.py')):
    try:
        compile(f.read_text(encoding='utf-8'), str(f), 'exec')
    except SyntaxError as e:
        print(f'  FAIL {f.name}: {e}')
        fail += 1
if fail == 0:
    print(f'  全部通过（{len(list(src.glob(\"*.py\")))} 个文件）')
    sys.exit(0)
sys.exit(1)
"
else
    echo "  未找到 python3，跳过"
fi
echo

# 4. 测试
echo "[4] 单元测试"
if command -v pytest >/dev/null 2>&1; then
    pytest tests/ -q 2>&1 | tail -3
else
    echo "  未找到 pytest，跳过（安装：pip install pytest）"
fi
echo

# 5. Git 状态
echo "[5] Git 状态"
if command -v git >/dev/null 2>&1; then
    git status -s 2>/dev/null | head -5
    last=$(git log --oneline -1 2>/dev/null)
    echo "  最新提交：$last"
else
    echo "  未找到 git"
fi
echo

echo "=== 自检完成 ==="
