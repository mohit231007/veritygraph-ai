from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from time import perf_counter
from uuid import uuid4

from app.core.config import get_settings
from app.domain.analysis import AnalysisRun, AnalysisStatus, WorkspaceAnalysis
from app.nlp.engine import SpacyNlpEngine
from app.nlp.resolver import DeterministicEntityResolver
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.source_repository import SourceRepository
from app.repositories.workspace_repository import WorkspaceRepository


class WorkspaceAnalysisError(ValueError):
    """Raised when a workspace cannot be analysed."""


class WorkspaceAnalysisNotFoundError(WorkspaceAnalysisError):
    """Raised when the requested workspace does not exist."""


class EmptyWorkspaceError(WorkspaceAnalysisError):
    """Raised when analysis is requested before any source is saved."""


@lru_cache
def get_nlp_engine() -> SpacyNlpEngine:
    settings = get_settings()
    return SpacyNlpEngine(
        model_name=settings.nlp_model,
        batch_size=settings.nlp_batch_size,
    )


def run_workspace_analysis(
    *,
    workspace_id: str,
    workspace_repository: WorkspaceRepository,
    source_repository: SourceRepository,
    analysis_repository: AnalysisRepository,
    engine: SpacyNlpEngine,
) -> WorkspaceAnalysis:
    """Run extraction plus conservative local entity resolution over a workspace."""

    workspace = workspace_repository.get(workspace_id)
    if workspace is None:
        raise WorkspaceAnalysisNotFoundError("Workspace not found.")
    if not workspace.sources:
        raise EmptyWorkspaceError("Add at least one source to the workspace before analysis.")

    bundles = []
    for source in workspace.sources:
        bundle = source_repository.get(source.source_id)
        if bundle is not None:
            bundles.append(bundle)
    if not bundles:
        raise EmptyWorkspaceError("Workspace has no readable persisted sources.")

    resolver = DeterministicEntityResolver()
    run_id = f"run_{uuid4().hex}"
    started_at = datetime.now(UTC)
    started_timer = perf_counter()
    span_count = sum(len(bundle.spans) for bundle in bundles)
    source_ids = [bundle.document.source_id for bundle in bundles]
    run = AnalysisRun(
        run_id=run_id,
        workspace_id=workspace_id,
        status=AnalysisStatus.RUNNING,
        pipeline_version=engine.PIPELINE_VERSION,
        model_name=engine.model_name,
        model_version=engine.model_version,
        extractor_version=engine.EXTRACTOR_VERSION,
        resolver_version=resolver.VERSION,
        started_at=started_at,
        source_count=len(bundles),
        source_ids=source_ids,
        span_count=span_count,
    )
    analysis_repository.save(WorkspaceAnalysis(run=run, entities=[], relations=[]))

    try:
        entities, relations = engine.extract(run_id=run_id, bundles=bundles)
        entities, relations = resolver.resolve(entities=entities, relations=relations)
    except Exception as exc:
        completed_at = datetime.now(UTC)
        run.status = AnalysisStatus.FAILED
        run.completed_at = completed_at
        run.duration_ms = max(0, int((perf_counter() - started_timer) * 1000))
        run.error = f"{type(exc).__name__}: {exc}"
        analysis_repository.save(WorkspaceAnalysis(run=run, entities=[], relations=[]))
        raise

    run.status = AnalysisStatus.COMPLETED
    run.completed_at = datetime.now(UTC)
    run.duration_ms = max(0, int((perf_counter() - started_timer) * 1000))
    run.entity_count = len(entities)
    run.relation_count = len(relations)
    analysis = WorkspaceAnalysis(run=run, entities=entities, relations=relations)
    return analysis_repository.save(analysis)
