# 私人 AI 知识库问答系统
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY rag-private-docs/requirements.txt ./rag-private-docs/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r rag-private-docs/requirements.txt

COPY rag-private-docs/ ./rag-private-docs/

WORKDIR /app/rag-private-docs/src

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
