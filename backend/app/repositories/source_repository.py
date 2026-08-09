from __future__ import annotations

from threading import RLock

from app.domain.source import SourceBundle


class InMemorySourceRepository:
    """Thread-safe local repository used until SQLite persistence lands.

    The interface is intentionally tiny so a SQLite implementation can replace this
    adapter without changing ingestion or API contracts.
    """

    def __init__(self) -> None:
        self._items: dict[str, SourceBundle] = {}
        self._lock = RLock()

    def save(self, bundle: SourceBundle) -> SourceBundle:
        with self._lock:
            self._items[bundle.document.source_id] = bundle
        return bundle

    def get(self, source_id: str) -> SourceBundle | None:
        with self._lock:
            return self._items.get(source_id)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


_repository = InMemorySourceRepository()


def get_source_repository() -> InMemorySourceRepository:
    return _repository
