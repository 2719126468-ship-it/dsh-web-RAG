"""FastAPI 接口层：把 RAG 能力暴露为 HTTP 接口。

启动：
    pip install fastapi uvicorn
    cd rag-private-docs/src
    uvicorn api:app --host 0.0.0.0 --port 8000

接口：
    GET  /health         健康检查
    POST /index          触发索引
    POST /query          问答
"""
import sys
from pathlib import Path
from typing import List, Optional

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
except ImportError:
    print("[warn] 未安装 fastapi/uvicorn。安装：pip install fastapi uvicorn")
    print("[warn] 本模块仅在装了 fastapi 后才能作为服务器运行")
    FastAPI = None
    BaseModel = object


if FastAPI is not None:
    app = FastAPI(title="DSH Web RAG API", version="1.0.0")

    class QueryRequest(BaseModel):
        question: str
        top_k: int = 5

    class QueryResponse(BaseModel):
        answer: str
        sources: List[dict] = []
        confidence: float = 0.0

    class IndexResponse(BaseModel):
        status: str
        summary: Optional[dict] = None

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "dsh-web-rag"}

    @app.post("/index", response_model=IndexResponse)
    def index(force: bool = False):
        try:
            from indexer import main as run_index
            summary = run_index(force=force)
            try:
                from webhook import notify_index_done
                notify_index_done(summary)
            except Exception:
                pass
            return {"status": "ok", "summary": summary}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"索引失败：{e}")

    @app.post("/query", response_model=QueryResponse)
    def query(req: QueryRequest):
        try:
            from qa import answer_question
        except ImportError:
            raise HTTPException(
                status_code=501,
                detail="qa 模块接口未适配，请根据 qa.py 实际函数名调整 /query 实现",
            )
        try:
            result = answer_question(req.question, top_k=req.top_k)
            if isinstance(result, dict):
                return QueryResponse(
                    answer=result.get("answer", ""),
                    sources=result.get("sources", []),
                    confidence=result.get("confidence", 0.0),
                )
            return QueryResponse(answer=str(result))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"查询失败：{e}")
else:
    app = None


if __name__ == "__main__":
    if app is None:
        print("请先安装 fastapi：pip install fastapi uvicorn")
        sys.exit(1)
    import uvicorn
    from config import config
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
