import logging
import os
import uuid

import redis
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel, Field

from app.core.CacheService import CacheService
from app.core.LLMService import LLMService
from app.core.QueryService import QueryService
from app.loadtest import run_loadtest

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")


app = FastAPI(title="semantic-llm-cache")


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    forceRefresh: bool = Field(default=False)

class QueryResponse(BaseModel):
    response: str
    metadata: dict[str, object]


class LoadTestRequest(BaseModel):
    users: int = Field(default=5, ge=1, le=2000)
    spawn_rate: int = Field(default=5, ge=1, le=500)
    run_time: str = Field(default="5s")


_redis = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    decode_responses=True,
)

_cache = CacheService(_redis)
_flow = QueryService(cache=_cache, ai=LLMService())


@app.post("/api/query", response_model=QueryResponse)
def query(req: QueryRequest, background_tasks: BackgroundTasks) -> QueryResponse:
    result = _flow.handle_query(req.query, req.forceRefresh)
    
    embedding = result.pop("_embedding", None)
    background_tasks.add_task(_flow.async_write_to_cache, req.query, result["response"], result.get("metadata", {}), embedding)

    return QueryResponse(**result) 


@app.get("/api/metrics")
def metrics() -> dict:
    return {
        "metrics": _cache.get_metrics()
    }


@app.post("/api/loadtest")
def loadtest(req: LoadTestRequest) -> dict:
    
    _cache.flush_all()
    run_id = uuid.uuid4().hex
    result = run_loadtest(run_id, "http://localhost:3000", req.users, req.spawn_rate, req.run_time)
    return {"run_id": run_id, "result": result}