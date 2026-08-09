from hashlib import sha256

from app.domain.source import (
    BibliographicIdentifierKind,
    IdentifierObservationRole,
    SourceBundle,
    SourceDocument,
    SourceReference,
    SourceSpan,
    SourceType,
)
from app.repositories.source_repository import SqliteSourceRepository
from app.services.source_identifiers import extract_source_identifiers


def _span(source_id: str, text: str) -> SourceSpan:
    return SourceSpan(
        span_id="span_identifiers",
        source_id=source_id,
        text=text,
        page_number=1,
        paragraph_number=1,
        char_start=0,
        char_end=len(text),
    )


def test_explicit_identifiers_are_normalized_conservatively() -> None:
    source_id = "src_identifiers"
    span = _span(
        source_id,
        "DOI:10.5594/SMPTE.ST2067-21.2020 "
        "arXiv:2208.12242v2 "
        "ISBN 978-0-306-40615-7 "
        "ISBN-10 0-306-40615-2 "
        "ISBN 978-0-306-40615-8",
    )

    identifiers = extract_source_identifiers(
        source_id=source_id,
        spans=[span],
        references=[],
    )

    assert [(item.kind, item.normalized_value) for item in identifiers] == [
        (BibliographicIdentifierKind.ARXIV, "2208.12242"),
        (BibliographicIdentifierKind.DOI, "10.5594/smpte.st2067-21.2020"),
        (BibliographicIdentifierKind.ISBN, "9780306406157"),
    ]
    arxiv = identifiers[0]
    assert arxiv.version == 2
    assert arxiv.role == IdentifierObservationRole.MENTION
    assert all(item.normalized_value != "9780306406158" for item in identifiers)


def test_doi_and_arxiv_reference_urls_are_reference_linked() -> None:
    source_id = "src_reference_ids"
    references = [
        SourceReference(
            reference_id="ref_doi",
            source_id=source_id,
            target_url="https://doi.org/10.1000/VERITY.TEST",
            normalized_target_url="https://doi.org/10.1000/VERITY.TEST",
            reference_text="Primary DOI source",
            extraction_method="fixture",
        ),
        SourceReference(
            reference_id="ref_arxiv",
            source_id=source_id,
            target_url="https://arxiv.org/pdf/2208.12242v3.pdf",
            normalized_target_url="https://arxiv.org/pdf/2208.12242v3.pdf",
            reference_text="Primary arXiv source",
            extraction_method="fixture",
        ),
    ]

    identifiers = extract_source_identifiers(
        source_id=source_id,
        spans=[],
        references=references,
    )

    assert len(identifiers) == 2
    doi = next(item for item in identifiers if item.kind == BibliographicIdentifierKind.DOI)
    arxiv = next(item for item in identifiers if item.kind == BibliographicIdentifierKind.ARXIV)
    assert doi.normalized_value == "10.1000/verity.test"
    assert doi.role == IdentifierObservationRole.REFERENCE
    assert doi.reference_id == "ref_doi"
    assert arxiv.normalized_value == "2208.12242"
    assert arxiv.version == 3
    assert arxiv.role == IdentifierObservationRole.REFERENCE
    assert arxiv.reference_id == "ref_arxiv"


def test_supported_acquisition_urls_attest_source_identity() -> None:
    identifiers = extract_source_identifiers(
        source_id="src_attested",
        spans=[],
        references=[],
        source_urls=[
            "https://doi.org/10.1000/VERITY.TEST",
            "https://arxiv.org/abs/2208.12242v4",
            "https://publisher.example/10.2000/not-an-attestation",
        ],
    )

    assert len(identifiers) == 2
    doi = next(item for item in identifiers if item.kind == BibliographicIdentifierKind.DOI)
    arxiv = next(item for item in identifiers if item.kind == BibliographicIdentifierKind.ARXIV)
    assert doi.normalized_value == "10.1000/verity.test"
    assert doi.role == IdentifierObservationRole.SOURCE_IDENTITY
    assert doi.context_text == "https://doi.org/10.1000/VERITY.TEST"
    assert arxiv.normalized_value == "2208.12242"
    assert arxiv.version == 4
    assert arxiv.role == IdentifierObservationRole.SOURCE_IDENTITY
    assert all("not-an-attestation" not in item.raw_value for item in identifiers)


def test_source_identifiers_survive_sqlite_reload(tmp_path) -> None:
    source_id = "src_sqlite_identifiers"
    text = "Dataset DOI:10.1000/VERITY.TEST and ISBN 978-0-306-40615-7"
    span = _span(source_id, text)
    identifiers = extract_source_identifiers(
        source_id=source_id,
        spans=[span],
        references=[],
        source_urls=["https://doi.org/10.1000/VERITY.TEST"],
    )
    document = SourceDocument(
        source_id=source_id,
        source_type=SourceType.PUBLIC_URL,
        title="Identifier source",
        url="https://doi.org/10.1000/VERITY.TEST",
        source_format="html",
        mime_type="text/html",
        content_hash=sha256(text.encode("utf-8")).hexdigest(),
        size_bytes=len(text.encode("utf-8")),
    )

    database = tmp_path / "identifiers.sqlite3"
    repository = SqliteSourceRepository(database)
    repository.save(
        SourceBundle(document=document, spans=[span], identifiers=identifiers)
    )

    reloaded = SqliteSourceRepository(database).get(source_id)
    assert reloaded is not None
    assert [(item.normalized_value, item.role) for item in reloaded.identifiers] == [
        ("10.1000/verity.test", IdentifierObservationRole.MENTION),
        ("10.1000/verity.test", IdentifierObservationRole.SOURCE_IDENTITY),
        ("9780306406157", IdentifierObservationRole.MENTION),
    ]
    identity = next(
        item
        for item in reloaded.identifiers
        if item.role == IdentifierObservationRole.SOURCE_IDENTITY
    )
    assert identity.span_id is None
    assert identity.context_text == "https://doi.org/10.1000/VERITY.TEST"
