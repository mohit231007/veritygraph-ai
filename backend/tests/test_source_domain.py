import pytest
from app.domain.source import SourceSpan
from pydantic import ValidationError


def test_source_span_rejects_reversed_offsets() -> None:
    with pytest.raises(ValidationError, match="char_end must be greater"):
        SourceSpan(
            span_id="span_test",
            source_id="src_test",
            text="evidence",
            char_start=10,
            char_end=5,
        )
