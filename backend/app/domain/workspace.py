from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.domain.source import SourceDocument


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)

    @field_validator("name", "description")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split()).strip()


class WorkspaceSummary(BaseModel):
    workspace_id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    source_count: int = Field(ge=0)


class WorkspaceDetail(WorkspaceSummary):
    sources: list[SourceDocument] = Field(default_factory=list)
