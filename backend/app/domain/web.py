from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator


class PublicUrlImportRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)

    @field_validator("url")
    @classmethod
    def strip_url(cls, value: str) -> str:
        normalized = value.strip()
        if any(ord(character) < 32 for character in normalized):
            raise ValueError("URL must not contain control characters")
        return normalized


@dataclass(slots=True, frozen=True)
class RawWebPage:
    requested_url: str
    final_url: str
    mime_type: str
    content: bytes
    redirect_count: int
    status_code: int
