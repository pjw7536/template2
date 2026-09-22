"""L3 Spider 계산 결과에 사용하는 작은 TTL 메모리 캐시입니다."""

from __future__ import annotations

import threading
import time
from typing import Any


class TTLCache:
    """스레드 안전하게 TTL 동안 값을 보관하는 프로세스 내부 캐시입니다."""

    def __init__(self, ttl: float = 600.0) -> None:
        """캐시 유효 시간을 초 단위로 설정합니다."""

        self._ttl = ttl
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any:
        """유효한 값을 반환하고 만료된 값은 즉시 제거합니다."""

        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            stored_at, value = entry
            if time.monotonic() - stored_at > self._ttl:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        """현재 monotonic 시각과 함께 값을 저장합니다."""

        with self._lock:
            self._store[key] = (time.monotonic(), value)

    def clear(self) -> None:
        """보관 중인 모든 값을 제거합니다."""

        with self._lock:
            self._store.clear()
