import os

import redis
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel, Field

from app.core.CacheRepository import CacheRepository
from app.core.LLMAgent import AIAgent
from app.core.QueryDecisionFlow import QueryDecisionFlow


app = FastAPI(title="semantic-llm-cache")


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)

class QueryResponse(BaseModel):
    response: str
    metadata: dict[str, object]


_redis = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    decode_responses=True,
)
_flow = QueryDecisionFlow(cache=CacheRepository(_redis), ai=AIAgent())


@app.post("/api/query", response_model=QueryResponse)
def query(req: QueryRequest, background_tasks: BackgroundTasks) -> QueryResponse:
    result = _flow.handle_query(req.query)
    
    embedding = result.pop("_embedding", None)
    source = result.get("metadata", {}).get("source")
    risk_level = result.get("metadata", {}).get("risk_level")
    
    #Asynchronously write to caches if query is from LLM and embedding is valid and risk level is not high
    if source == "llm" and embedding is not None and risk_level != "high":
        background_tasks.add_task(_flow.async_write_to_caches, req.query, result["response"], embedding)

    return QueryResponse(**result)

