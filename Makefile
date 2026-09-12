.PHONY: help test lint format index reindex run docker-build docker-run clean

help:
@echo "make test / lint / format / index / reindex / run / docker-build / docker-run / clean"

test:
python -m pytest tests/ -v

lint:
ruff check rag-private-docs/src/ tests/

format:
ruff format rag-private-docs/src/ tests/

index:
cd rag-private-docs/src && python indexer.py

reindex:
cd rag-private-docs/src && python indexer.py --force

run:
cd rag-private-docs/src && streamlit run app.py

docker-build:
docker build -t dsh-web-rag .

docker-run:
docker run --rm -p 8501:8501 --env-file rag-private-docs/.env dsh-web-rag

clean:
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
rm -rf .ruff_cache 2>/dev/null || true
