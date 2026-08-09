from fastapi import APIRouter
from pydantic import BaseModel

from app.version import VERSION

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return the smallest contract used by smoke tests and orchestration."""
    return HealthResponse(status="healthy", service="veritygraph-api", version=VERSION)
