from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Dict, Iterable, Mapping, Optional

from django.http import HttpRequest, HttpResponse
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

    TRACKED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def process_request(self, request: HttpRequest) -> None:
        """초기 컨텍스트 설정 및 요청 페이로드 스냅샷."""

        context = getattr(request, "_activity_log_context", None)
        if context is None:
            context = {}
            setattr(request, "_activity_log_context", context)

        if request.method in self.TRACKED_METHODS:
            context["request_payload"] = self._extract_request_payload(request)

    def process_response(self, request: HttpRequest, response: HttpResponse):
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

    def _record(self, request: HttpRequest, response: HttpResponse) -> None:
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
        context: Dict[str, Any] = getattr(request, "_activity_log_context", {})

        metadata: Dict[str, Any] = {
            # GET 파라미터를 dict로 변환해 저장
            "query": request.GET.dict() if hasattr(request, "GET") else {},
            "result": "ok"
            if getattr(response, "status_code", 200) < 400
            else "fail",
        }

        # 내부 컨테이너 IP(172.18.0.1)는 저장하지 않음
        remote_addr = request.META.get("REMOTE_ADDR")
        if remote_addr and remote_addr != "172.18.0.1":
            metadata["remote_addr"] = remote_addr

        extra_metadata: Mapping[str, Any] = context.get("extra_metadata") or {}
        metadata.update(extra_metadata)

        if metadata["result"] == "ok" and request.method in self.TRACKED_METHODS:
            before = context.get("before")
            after = context.get("after")
            change_set = context.get("changes")
            if not change_set:
                change_set = self._compute_diff(before, after)
            normalized_changes = self._normalize_change_set(change_set)
            if normalized_changes:
                metadata["changes"] = normalized_changes
        elif metadata["result"] == "fail":
            error_payload = self._extract_response_payload(response)
            if error_payload is not None:
                try:
                    metadata["error"] = json.dumps(
                        error_payload, ensure_ascii=False
                    )
                except TypeError:
                    metadata["error"] = str(error_payload)
            else:
                status_text = getattr(response, "reason_phrase", None)
                if status_text:
                    metadata["error"] = status_text

        # 실제 ActivityLog 테이블에 로그 행 생성
        ActivityLog.objects.create(
            user=user,  # 인증된 사용자 또는 None
            # 뷰 이름 (URLconf에 name이 지정된 경우 자동 추적)
            action=context.get("summary")
            or (
                request.resolver_match.view_name
                if getattr(request, "resolver_match", None)
                else ""
            ),
            path=path,  # 요청 경로 (예: /api/tables)
            method=getattr(request, "method", "GET"),  # 요청 HTTP 메서드
            status_code=getattr(response, "status_code", 200),  # 응답 상태 코드
            metadata=metadata,  # 부가 정보 (쿼리, IP 등)
        )

    def _extract_request_payload(self, request: HttpRequest) -> Optional[Any]:
        """요청 본문을 JSON으로 파싱하거나 텍스트로 스냅샷 저장."""

        try:
            body = request.body
        except Exception:  # pragma: no cover - best effort
            return None

        if not body:
            return None

        try:
            return json.loads(body.decode(request.encoding or "utf-8"))
        except Exception:
            try:
                return body.decode(request.encoding or "utf-8", errors="replace")
            except Exception:
                return None

    def _extract_response_payload(self, response: HttpResponse) -> Optional[Any]:
        """응답 본문을 JSON으로 파싱."""

        if not hasattr(response, "content"):
            return None

        try:
            content = response.content
        except Exception:  # pragma: no cover - best effort
            return None

        if not content:
            return None

        try:
            return json.loads(content.decode(response.charset or "utf-8"))
        except Exception:
            return None

    def _compute_diff(
        self, before: Optional[Any], after: Optional[Any]
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """딕셔너리 기반의 변경 사항을 계산."""

        if not isinstance(after, Mapping):
            return None

        if not isinstance(before, Mapping):
            return {
                key: {"old": None, "new": value}
                for key, value in after.items()
            } or None

        diff: Dict[str, Dict[str, Any]] = {}
        keys: Iterable[str] = set(before.keys()) | set(after.keys())
        for key in keys:
            old_value = before.get(key)
            new_value = after.get(key)
            if old_value != new_value:
                diff[key] = {"old": old_value, "new": new_value}

        return diff or None

    def _normalize_change_set(
        self, changes: Optional[Any]
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """변경 사항을 {old, new} 구조로 정규화."""

        if not isinstance(changes, Mapping):
            return None

        normalized: Dict[str, Dict[str, Any]] = {}
        for field, payload in changes.items():
            if isinstance(payload, Mapping):
                old_value = payload.get("old", payload.get("from"))
                new_value = payload.get("new", payload.get("to"))
            else:
                old_value = None
                new_value = payload

            if old_value is None and new_value is None:
                continue

            normalized[field] = {
                "old": self._sanitize_json_value(old_value),
                "new": self._sanitize_json_value(new_value),
            }

        return normalized or None

    def _sanitize_json_value(self, value: Any) -> Any:
        """ActivityLog 메타데이터에 저장하기 위해 JSON 직렬화 가능한 값으로 변환."""

        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except Exception:
                return value.decode("utf-8", errors="replace")
        if isinstance(value, Mapping):
            return {k: self._sanitize_json_value(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._sanitize_json_value(v) for v in value]

        # json.dumps 가능 여부를 검사하여 불가능하면 문자열로 변환
        try:
            json.dumps(value)
            return value
        except TypeError:
            return str(value)
