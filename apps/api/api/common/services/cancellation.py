# =============================================================================
# 모듈: 외부 호출 취소 신호
# 주요 클래스: ExternalCallCancellation, ExternalCallCancelled
# 핵심 전제: 취소 callback은 여러 번 호출돼도 안전해야 합니다.
# =============================================================================
"""worker와 HTTP transport 사이에서 공유하는 thread-safe 취소 신호입니다."""

from __future__ import annotations

from collections.abc import Callable
import threading


class ExternalCallCancelled(RuntimeError):
    """사용자 중단 또는 실행 timeout으로 외부 호출이 취소됐음을 나타냅니다."""


class ExternalCallCancellation:
    """취소 상태와 현재 열린 외부 resource close callback을 관리합니다."""

    def __init__(self) -> None:
        """빈 취소 신호를 생성합니다."""

        self._event = threading.Event()
        self._lock = threading.Lock()
        self._closers: set[Callable[[], object]] = set()

    @property
    def cancelled(self) -> bool:
        """취소 요청 여부를 반환합니다."""

        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        """취소 상태이면 worker 실행을 즉시 중단합니다."""

        if self.cancelled:
            raise ExternalCallCancelled("외부 호출이 취소되었습니다.")

    def register_closer(self, closer: Callable[[], object]) -> Callable[[], None]:
        """열린 resource closer를 등록하고 해제 함수를 반환합니다."""

        with self._lock:
            if self.cancelled:
                should_close = True
            else:
                self._closers.add(closer)
                should_close = False
        if should_close:
            self._close_safely(closer)

        def unregister() -> None:
            """등록된 closer를 취소 callback 집합에서 제거합니다."""

            with self._lock:
                self._closers.discard(closer)

        return unregister

    def cancel(self) -> None:
        """취소 상태를 설정하고 현재 열린 resource를 닫습니다."""

        self._event.set()
        with self._lock:
            closers = list(self._closers)
            self._closers.clear()
        for closer in closers:
            self._close_safely(closer)

    @staticmethod
    def _close_safely(closer: Callable[[], object]) -> None:
        """취소 경로에서 close 예외가 원래 종료 흐름을 가리지 않게 합니다."""

        try:
            closer()
        except Exception:
            return


__all__ = ["ExternalCallCancellation", "ExternalCallCancelled"]
