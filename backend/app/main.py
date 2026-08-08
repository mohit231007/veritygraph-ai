from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_documents import router as documents_router
from app.api.routes_health import router as health_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="VerityGraph AI API",
    description="Evidence-grounded document and web intelligence API.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"service": "veritygraph-api", "docs": "/docs"}
