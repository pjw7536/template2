# =============================================================================
# 모듈 설명: 활동 로그 컨텍스트를 요청에 누적하는 헬퍼를 제공합니다.
# - 주요 대상: set_activity_summary, set_activity_previous_state, set_activity_new_state
# - 불변 조건: 컨텍스트는 요청 단위 dict로 유지됩니다.
# =============================================================================

"""활동 로그에 필요한 부가 정보를 요청 객체에 누적하는 헬퍼 모음.

- 주요 대상: 요청(HttpRequest)의 `_activity_log_context` 딕셔너리
- 주요 엔드포인트/클래스: 없음(함수형 헬퍼만 제공)
- 가정/불변 조건: 컨텍스트는 요청 단위이며 dict 형태로 유지됨
"""
from __future__ import annotations

from typing import Any, Dict, MutableMapping, Optional

from django.http import HttpRequest


ContextDict = MutableMapping[str, Any]


def _ensure_context(request: HttpRequest) -> ContextDict:
    """요청 단위 활동 로그 컨텍스트를 준비해 반환합니다.

    입력:
    - 요청: Django HttpRequest

    반환:
    - ContextDict: 요청에 바인딩된 컨텍스트 딕셔너리

    부작용:
    - request에 `_activity_log_context` 속성이 없으면 새로 생성

    오류:
    - 없음(속성 접근/설정 실패 시 상위 예외가 전파됨)
    """

    context = getattr(request, "_activity_log_context", None)
    if context is None:
        context = {}
        setattr(request, "_activity_log_context", context)
    return context


def set_activity_summary(request: HttpRequest, summary: str) -> None:
    """요청에서 수행 중인 작업 요약을 컨텍스트에 기록합니다.

    입력:
    - 요청: Django HttpRequest
    - summary: 사람이 읽을 수 있는 작업 요약 문자열

    반환:
    - 없음

    부작용:
    - request의 컨텍스트에 `summary` 키를 설정

    오류:
    - 없음(키 설정 실패 시 상위 예외가 전파됨)
    """

    context = _ensure_context(request)
    context["summary"] = summary


def set_activity_previous_state(request: HttpRequest, data: Optional[Any]) -> None:
    """변경 전 상태를 활동 로그 컨텍스트에 기록합니다.

    입력:
    - 요청: Django HttpRequest
    - data: 변경 전 상태(직렬화 가능한 값)

    반환:
    - 없음

    부작용:
    - request의 컨텍스트에 `before` 키를 설정

    오류:
    - 없음(키 설정 실패 시 상위 예외가 전파됨)
    """

    context = _ensure_context(request)
    context["before"] = data


def set_activity_new_state(request: HttpRequest, data: Optional[Any]) -> None:
    """변경 후 상태를 활동 로그 컨텍스트에 기록합니다.

    입력:
    - 요청: Django HttpRequest
    - data: 변경 후 상태(직렬화 가능한 값)

    반환:
    - 없음

    부작용:
    - request의 컨텍스트에 `after` 키를 설정

    오류:
    - 없음(키 설정 실패 시 상위 예외가 전파됨)
    """

    context = _ensure_context(request)
    context["after"] = data


def merge_activity_metadata(request: HttpRequest, **extra: Any) -> None:
    """활동 로그에 저장할 추가 메타데이터를 병합합니다.

    입력:
    - 요청: Django HttpRequest
    - **extra: 추가 메타데이터 키-값

    반환:
    - 없음

    부작용:
    - request의 컨텍스트에 `extra_metadata`를 병합

    오류:
    - 없음(딕셔너리 갱신 실패 시 상위 예외가 전파됨)
    """

    context = _ensure_context(request)
    metadata: Dict[str, Any] = context.setdefault("extra_metadata", {})
    metadata.update(extra)


__all__ = [
    "merge_activity_metadata",
    "set_activity_new_state",
    "set_activity_previous_state",
    "set_activity_summary",
]
