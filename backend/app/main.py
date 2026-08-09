from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_analysis import router as analysis_router
from app.api.routes_comparison import router as comparison_router
from app.api.routes_documents import router as documents_router
from app.api.routes_graph import router as graph_router
from app.api.routes_health import router as health_router
from app.api.routes_lineage import router as lineage_router
from app.api.routes_retrieval import router as retrieval_router
from app.api.routes_sources import router as sources_router
from app.api.routes_web import router as web_router
from app.api.routes_wikipedia import router as wikipedia_router
from app.api.routes_workspaces import router as workspaces_router
from app.core.config import get_settings
from app.version import VERSION

settings = get_settings()

app = FastAPI(
    title="VerityGraph AI API",
    description="Evidence-grounded document and web intelligence API.",
    version=VERSION,
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
app.include_router(wikipedia_router, prefix="/api/v1")
app.include_router(web_router, prefix="/api/v1")
app.include_router(sources_router, prefix="/api/v1")
app.include_router(workspaces_router, prefix="/api/v1")
app.include_router(lineage_router, prefix="/api/v1")
app.include_router(retrieval_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(graph_router, prefix="/api/v1")
app.include_router(comparison_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"service": "veritygraph-api", "docs": "/docs"}
