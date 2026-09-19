from fastapi import APIRouter, Request
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request) -> dict[str, str]:
    engine = request.app.state.engine
    redis = request.app.state.redis
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    await redis.ping()
    return {"status": "ok"}
