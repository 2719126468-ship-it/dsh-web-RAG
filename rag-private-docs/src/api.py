"""Authenticated FastAPI interface for DSH Web RAG.

Run locally:
    uvicorn api:app --host 127.0.0.1 --port 8000

Set API_AUTH_TOKEN for queries and API_ADMIN_TOKEN for index management.
The health endpoint is intentionally public and returns no sensitive details.
"""
import hmac
import logging
import sys
from pathlib import Path
from typing import List, Optional

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))

try:
    from fastapi import FastAPI, Header, HTTPException, Depends
    from pydantic import BaseModel, Field
except ImportError:
    print("[warn] FastAPI is not installed. Install fastapi and uvicorn to run this API.")
    FastAPI = None
    BaseModel = object

logger = logging.getLogger(__name__)


if FastAPI is not None:
    from config import config

    app = FastAPI(
        title="DSH Web RAG API",
        version="1.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    class QueryRequest(BaseModel):
        question: str = Field(min_length=1, max_length=8000)
        top_k: int = Field(default=5, ge=1, le=20)

    class QueryResponse(BaseModel):
        answer: str
        sources: List[dict] = Field(default_factory=list)
        confidence: float = 0.0

    class IndexResponse(BaseModel):
        status: str
        summary: Optional[dict] = None

    def _require_token(expected: str, authorization: Optional[str], scope: str) -> None:
        if not expected:
            raise HTTPException(
                status_code=503,
                detail=f"{scope} authentication is not configured",
            )
        scheme, _, supplied = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not supplied or not hmac.compare_digest(
            supplied, expected
        ):
            raise HTTPException(status_code=401, detail="Invalid or missing bearer token")

    def require_api_token(
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ) -> None:
        _require_token(config.API_AUTH_TOKEN, authorization, "API")

    def require_admin_token(
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ) -> None:
        _require_token(config.API_ADMIN_TOKEN, authorization, "Admin")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "dsh-web-rag"}

    @app.post("/index", response_model=IndexResponse)
    def index(
        force: bool = False,
        confirm_force: Optional[str] = Header(default=None, alias="X-Confirm-Force"),
        _authorized: None = Depends(require_admin_token),
    ):
        if force and (confirm_force or "").lower() != "true":
            raise HTTPException(
                status_code=400,
                detail="Force reindex requires X-Confirm-Force: true",
            )
        try:
            from indexer import main as run_index

            summary = run_index(force=force)
            try:
                from webhook import notify_index_done

                notify_index_done(summary)
            except Exception:
                logger.warning("Index webhook notification failed", exc_info=True)
            return {"status": "ok", "summary": summary}
        except HTTPException:
            raise
        except Exception:
            logger.exception("Index operation failed")
            raise HTTPException(status_code=500, detail="Index operation failed") from None

    _engine_holder = {"engine": None}

    def _get_engine():
        if _engine_holder["engine"] is None:
            from qa import RAGEngine

            _engine_holder["engine"] = RAGEngine()
        return _engine_holder["engine"]

    @app.post("/query", response_model=QueryResponse)
    def query(
        req: QueryRequest,
        _authorized: None = Depends(require_api_token),
    ):
        try:
            result = _get_engine().query(req.question.strip(), top_k=req.top_k)
            return QueryResponse(
                answer=result.get("answer", ""),
                sources=result.get("sources", []),
                confidence=result.get("confidence", 0.0),
            )
        except Exception:
            logger.exception("Query operation failed")
            raise HTTPException(status_code=500, detail="Query operation failed") from None
else:
    app = None


if __name__ == "__main__":
    if app is None:
        print("Please install FastAPI and uvicorn before starting the API.")
        sys.exit(1)
    import uvicorn
    from config import config

    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
