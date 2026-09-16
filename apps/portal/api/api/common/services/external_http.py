# =============================================================================
# 모듈: 공용 외부 HTTP transport
# 주요 함수: request_external
# 핵심 전제: provider payload와 공개 오류 문구는 호출 domain이 소유합니다.
# =============================================================================
"""외부 HTTP 호출의 timeout, 취소, transport 오류를 일관되게 분류합니다."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import requests

from .cancellation import ExternalCallCancellation, ExternalCallCancelled


class ExternalHttpError(RuntimeError):
    """외부 HTTP transport가 안전하게 정규화한 기본 오류입니다."""


class ExternalHttpTimeout(ExternalHttpError):
    """외부 HTTP 연결 또는 응답 대기 timeout입니다."""

    def __init__(self, *, phase: str) -> None:
        """timeout 단계만 보존하고 provider 상세는 노출하지 않습니다."""

        super().__init__("외부 서비스 응답 시간이 초과되었습니다.")
        self.phase = phase


class ExternalHttpResponseError(ExternalHttpError):
    """외부 서비스가 성공이 아닌 HTTP 상태를 반환한 오류입니다."""

    def __init__(self, *, status_code: int | None) -> None:
        """응답 상태 코드만 보존하고 본문은 노출하지 않습니다."""

        super().__init__("외부 서비스 요청에 실패했습니다.")
        self.status_code = status_code


def request_external(
    requester: Callable[..., requests.Response],
    url: str,
    *,
    timeout: int | float | tuple[int | float, int | float],
    cancellation: ExternalCallCancellation | None = None,
    raise_for_status: bool = False,
    **kwargs: Any,
) -> requests.Response:
    """주입된 requests 호출기로 외부 요청을 보내고 실패 종류를 정규화합니다."""

    if cancellation is not None:
        cancellation.raise_if_cancelled()
    try:
        response = requester(url, timeout=timeout, **kwargs)
        if cancellation is not None and cancellation.cancelled:
            response.close()
            raise ExternalCallCancelled("외부 호출이 취소되었습니다.")
        if raise_for_status:
            response.raise_for_status()
        return response
    except ExternalCallCancelled:
        raise
    except requests.ConnectTimeout as exc:
        if cancellation is not None and cancellation.cancelled:
            raise ExternalCallCancelled("외부 호출이 취소되었습니다.") from exc
        raise ExternalHttpTimeout(phase="connect") from exc
    except requests.ReadTimeout as exc:
        if cancellation is not None and cancellation.cancelled:
            raise ExternalCallCancelled("외부 호출이 취소되었습니다.") from exc
        raise ExternalHttpTimeout(phase="read") from exc
    except requests.Timeout as exc:
        if cancellation is not None and cancellation.cancelled:
            raise ExternalCallCancelled("외부 호출이 취소되었습니다.") from exc
        raise ExternalHttpTimeout(phase="unknown") from exc
    except requests.HTTPError as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        raise ExternalHttpResponseError(status_code=status_code) from exc
    except requests.RequestException as exc:
        if cancellation is not None and cancellation.cancelled:
            raise ExternalCallCancelled("외부 호출이 취소되었습니다.") from exc
        raise ExternalHttpError("외부 서비스에 연결하지 못했습니다.") from exc


__all__ = [
    "ExternalHttpError",
    "ExternalHttpResponseError",
    "ExternalHttpTimeout",
    "request_external",
]
