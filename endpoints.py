from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Any, Dict

from gateway import aggregate

router = APIRouter()


class AggregateRequest(BaseModel):
    urls: List[HttpUrl] = Field(..., min_items=1, description="Список URL для опроса")
    strategy: str = Field(default="fixed", pattern="^(fixed|timeout_race|adaptive)$")
    max_concurrent: Optional[int] = Field(default=3, ge=1, le=50)
    timeout_sec: Optional[float] = Field(default=5.0, ge=0.1, le=60.0)


class AggregateResponse(BaseModel):
    request_id: str
    results: List[Dict[str, Any]]
    summary: Dict[str, Any]
    adaptive_stats: Optional[Dict[str, Dict[str, Any]]] = None


@router.post("/aggregate", response_model=AggregateResponse)
async def post_aggregate(request: AggregateRequest):
    try:
        result = await aggregate(
            urls=[str(u) for u in request.urls],
            strategy=request.strategy,
            max_concurrent=request.max_concurrent,
            timeout_sec=request.timeout_sec
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "async-gateway"}


@router.get("/stats")
async def get_stats():
    from stats import stats_registry
    return stats_registry.get_all_stats()