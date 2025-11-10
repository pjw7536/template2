from __future__ import annotations

import logging
from typing import Any, Dict

from django.utils.deprecation import MiddlewareMixin  # Django 미들웨어 호환성 클래스
from .models import ActivityLog  # 사용자 활동 로그를 저장할 모델 (프로젝트별 정의)

# 현재 파일의 로거(logger) 설정
logger = logging.getLogger(__name__)


class ActivityLoggingMiddleware(MiddlewareMixin):
    """
    ✅ 사용자 요청/응답을 감시하고 ActivityLog 모델에 기록하는 미들웨어.

    [기능 요약]
    - 인증된 사용자 요청만 기록(비로그인 사용자는 user=None)
    - 관리자 페이지(/admin/)나 시스템용 경로(/__ 등)는 기록하지 않음
    - 요청 경로, 메서드, 응답 코드, 쿼리 파라미터, 클라이언트 IP 등을 저장
    """

    def process_response(self, request, response):
        """
        🔹 응답이 만들어진 뒤 호출됨 (모든 요청이 지나감)
        - 이 시점에 로그를 DB에 저장.
        - 로그 저장 중 에러가 나더라도 실제 응답 처리를 방해하지 않음.
        """
        try:
            # 실제 로그 생성 함수 호출
            self._record(request, response)
        except Exception:  # pragma: no cover - 테스트 제외
            # 로그 저장에 실패하더라도 서비스 중단 없이 에러만 기록
            logger.exception("Failed to record activity log")

        # 원래의 응답 객체를 그대로 반환
        return response

    def _record(self, request, response) -> None:
        """
        🔹 로그 레코드 생성 (ActivityLog 테이블에 1행 추가)
        """
        # CORS preflight 요청(OPTIONS)은 무시
        if request.method == "OPTIONS":
            return

        # 요청 경로 추출 (없을 경우 안전하게 빈 문자열)
        path = getattr(request, "path", "") or ""

        # admin 페이지나 Django 내부 경로는 기록하지 않음
        if path.startswith("/admin/") or path.startswith("/__"):
            return

        # 인증 사용자 확인 (비로그인 사용자는 None으로 처리)
        user = getattr(request, "user", None)
        if user is not None and not getattr(user, "is_authenticated", False):
            user = None

        # 요청 관련 메타데이터 (선택적으로 저장)
        metadata: Dict[str, Any] = {
            # GET 파라미터를 dict로 변환해 저장
            "query": request.GET.dict() if hasattr(request, "GET") else {},
            # 요청 보낸 클라이언트의 IP 주소
            "remote_addr": request.META.get("REMOTE_ADDR"),
        }

        # 실제 ActivityLog 테이블에 로그 행 생성
        ActivityLog.objects.create(
            user=user,  # 인증된 사용자 또는 None
            # 뷰 이름 (URLconf에 name이 지정된 경우 자동 추적)
            action=request.resolver_match.view_name if getattr(request, "resolver_match", None) else "",
            path=path,  # 요청 경로 (예: /api/tables)
            method=getattr(request, "method", "GET"),  # 요청 HTTP 메서드
            status_code=getattr(response, "status_code", 200),  # 응답 상태 코드
            metadata=metadata,  # 부가 정보 (쿼리, IP 등)
        )
