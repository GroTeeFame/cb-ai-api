from fastapi import APIRouter

router = APIRouter()


@router.get("/ready", tags=["health"])
async def readiness_probe() -> dict[str, str]:
    """Kubernetes/monitoring readiness probe."""
    return {"status": "ok"}


@router.get("/live", tags=["health"])
async def liveness_probe() -> dict[str, str]:
    """Simple liveness check."""
    return {"status": "alive"}

