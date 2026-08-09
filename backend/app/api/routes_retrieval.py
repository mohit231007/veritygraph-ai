from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.evidence_pack import EvidencePackRequest, GroundedEvidencePack
from app.domain.retrieval import RetrievalPreviewRequest, WorkspaceRetrievalPreview
from app.domain.retrieval_evaluation import (
    RetrievalEvaluationRequest,
    WorkspaceRetrievalEvaluation,
)
from app.repositories.source_repository import SourceRepository, get_source_repository
from app.repositories.workspace_repository import (
    WorkspaceRepository,
    get_workspace_repository,
)
from app.services.evidence_pack import build_grounded_evidence_pack
from app.services.retrieval import build_workspace_retrieval_preview
from app.services.retrieval_evaluation import (
    RetrievalEvaluationError,
    evaluate_workspace_retrieval,
)

router = APIRouter(prefix="/workspaces", tags=["retrieval"])
WorkspaceRepositoryDependency = Annotated[
    WorkspaceRepository,
    Depends(get_workspace_repository),
]
SourceRepositoryDependency = Annotated[
    SourceRepository,
    Depends(get_source_repository),
]


def _workspace_or_404(
    workspace_id: str,
    repository: WorkspaceRepository,
):
    workspace = repository.get(workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )
    return workspace


@router.post(
    "/{workspace_id}/retrieval/preview",
    response_model=WorkspaceRetrievalPreview,
    summary="Preview deterministic provenance-first span retrieval",
)
def preview_workspace_retrieval(
    workspace_id: str,
    request: RetrievalPreviewRequest,
    workspace_repository: WorkspaceRepositoryDependency,
    source_repository: SourceRepositoryDependency,
) -> WorkspaceRetrievalPreview:
    workspace = _workspace_or_404(workspace_id, workspace_repository)
    return build_workspace_retrieval_preview(
        workspace,
        query=request.query,
        limit=request.limit,
        source_repository=source_repository,
    )


@router.post(
    "/{workspace_id}/retrieval/evidence-pack",
    response_model=GroundedEvidencePack,
    summary="Assemble a deterministic budgeted evidence pack from directly retrieved spans",
)
def build_workspace_evidence_pack_route(
    workspace_id: str,
    request: EvidencePackRequest,
    workspace_repository: WorkspaceRepositoryDependency,
    source_repository: SourceRepositoryDependency,
) -> GroundedEvidencePack:
    workspace = _workspace_or_404(workspace_id, workspace_repository)
    return build_grounded_evidence_pack(
        workspace,
        query=request.query,
        max_excerpts=request.max_excerpts,
        max_excerpts_per_source=request.max_excerpts_per_source,
        max_chars_per_excerpt=request.max_chars_per_excerpt,
        max_total_chars=request.max_total_chars,
        source_repository=source_repository,
    )


@router.post(
    "/{workspace_id}/retrieval/evaluate",
    response_model=WorkspaceRetrievalEvaluation,
    summary="Evaluate the production ranker against explicit relevant-span labels",
)
def evaluate_workspace_retrieval_route(
    workspace_id: str,
    request: RetrievalEvaluationRequest,
    workspace_repository: WorkspaceRepositoryDependency,
    source_repository: SourceRepositoryDependency,
) -> WorkspaceRetrievalEvaluation:
    workspace = _workspace_or_404(workspace_id, workspace_repository)
    try:
        return evaluate_workspace_retrieval(
            workspace,
            cases=request.cases,
            k_values=request.k_values,
            source_repository=source_repository,
        )
    except RetrievalEvaluationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
