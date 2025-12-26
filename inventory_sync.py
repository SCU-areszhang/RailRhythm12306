from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import time


@dataclass(frozen=True)
class SyncReport:
    train_id: str
    redis_value: int
    db_value: int
    sync_latency_ms: int


class InventorySyncValidator:
    def __init__(
        self,
        redis_reader: Callable[[str], int],
        db_reader: Callable[[str], int],
        latency_provider: Callable[[], int] | None = None,
    ) -> None:
        self._redis_reader = redis_reader
        self._db_reader = db_reader
        self._latency_provider = latency_provider

    def perform_cross_check(self, train_id: str) -> SyncReport:
        start = time.perf_counter()
        redis_value = self._redis_reader(train_id)
        db_value = self._db_reader(train_id)
        latency_ms = (
            self._latency_provider()
            if self._latency_provider is not None
            else int((time.perf_counter() - start) * 1000)
        )
        return SyncReport(
            train_id=train_id,
            redis_value=redis_value,
            db_value=db_value,
            sync_latency_ms=latency_ms,
        )
