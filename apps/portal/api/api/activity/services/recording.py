# =============================================================================
# 모듈 설명: 일반 활동과 앱 화면 진입 이벤트 기록을 담당합니다.
# - 불변 조건: APP_ACCESS metadata의 저장 키는 기존 분석 selector와 호환됩니다.
# =============================================================================
from __future__ import annotations

from typing import Any

from ..models import ActivityLog
from ..selectors import APP_ACCESS_ACTION


def record_activity_log(
    *,
    user: Any | None,
    action: str,
    path: str,
    method: str,
    status_code: int,
    metadata: dict[str, Any],
) -> ActivityLog:
    """ActivityLog 행을 생성합니다.

    입력:
    - user: 인증 사용자 또는 None
    - action: 요청을 설명하는 액션 이름
    - path: 요청 경로
    - method: HTTP 메서드
    - status_code: 응답 상태 코드
    - metadata: 요청/응답 부가 정보

    반환:
    - ActivityLog: 생성된 활동 로그 인스턴스

    부작용:
    - ActivityLog 테이블에 행을 생성합니다.

    오류:
    - DB 저장 실패 시 Django ORM 예외가 발생할 수 있습니다.
    """

    return ActivityLog.objects.create(
        user=user,
        action=action,
        path=path,
        method=method,
        status_code=status_code,
        metadata=metadata,
    )


def record_app_access(
    *,
    user: Any,
    app_id: str,
    app_name: str,
    path: str,
) -> ActivityLog:
    """앱 화면 진입 이벤트를 ActivityLog에 기록합니다.

    입력:
    - user: 인증 사용자
    - app_id: 앱 식별자
    - app_name: 앱 표시 이름
    - path: 프론트엔드 경로

    반환:
    - ActivityLog: 생성된 앱 접속 이벤트

    부작용:
    - ActivityLog 테이블에 APP_ACCESS 행을 생성합니다.

    오류:
    - DB 저장 실패 시 Django ORM 예외가 발생할 수 있습니다.
    """

    return record_activity_log(
        user=user,
        action=APP_ACCESS_ACTION,
        path=path or f"/app-access/{app_id}",
        method="EVENT",
        status_code=200,
        metadata={
            "event_type": "app_access",
            "app_id": app_id,
            "app_name": app_name,
            "knox_id": getattr(user, "knox_id", "") or "",
        },
    )
