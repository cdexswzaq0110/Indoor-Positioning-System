"""Fix 的即時狀態與歷史軌跡。雛型階段放記憶體，重啟即清空。"""
from __future__ import annotations

import threading
from collections import defaultdict, deque

from .schemas import Fix


class PositionStore:
    def __init__(self, history_limit: int) -> None:
        self._lock = threading.Lock()
        self._current: dict[str, Fix] = {}
        self._history: dict[str, deque[Fix]] = defaultdict(
            lambda: deque(maxlen=history_limit)
        )

    def record(self, fix: Fix) -> None:
        with self._lock:
            self._current[fix.device_id] = fix
            self._history[fix.device_id].append(fix)

    def current(self, device_id: str) -> Fix | None:
        with self._lock:
            return self._current.get(device_id)

    def all_current(self) -> list[Fix]:
        with self._lock:
            return list(self._current.values())

    def history(self, device_id: str, limit: int = 50) -> list[Fix]:
        with self._lock:
            items = list(self._history.get(device_id, ()))
        return items[-limit:]

    def clear(self) -> None:
        with self._lock:
            self._current.clear()
            self._history.clear()
