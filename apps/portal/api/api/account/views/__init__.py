# =============================================================================
# 모듈 설명: account 도메인 APIView를 제공합니다.
# - 주요 대상: 소속 변경/승인/재확인, 권한 부여, 외부 동기화
# - 불변 조건: 비즈니스 로직은 서비스/셀렉터로 위임합니다.
# =============================================================================

"""계정 도메인 APIView 모음.

- 주요 대상: 소속 변경, 개요 조회, 승인/목록, 외부 동기화, 권한 부여
- 주요 엔드포인트/클래스: AccountAffiliationView 등
- 가정/불변 조건: 비즈니스 처리는 서비스 레이어에 위임함
"""
from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.services import normalize_text, parse_json_body

from .. import selectors, services
from ..serializers import (
    AccessAuditLogQuerySerializer,
    BulkApprovePendingAccessRequestSerializer,
    BulkApplyAccessPolicyRuleSerializer,
    ApplyAllUserAccessSerializer,
    AccessMatrixQuerySerializer,
    AccessPolicyRuleCreateSerializer,
    AccessPolicyRuleQuerySerializer,
    AccessPolicyRuleUpdateSerializer,
    AccessRequestSerializer,
    AccessUserQuerySerializer,
    AccessUserDecisionSerializer,
    UserScopeAffiliationDataQuerySerializer,
    UserScopeAffiliationDataUpdateSerializer,
    PendingAccessRequestQuerySerializer,
    AffiliationApprovalSerializer,
    AffiliationChangeRequestSerializer,
    AffiliationMembersQuerySerializer,
    AffiliationRequestQuerySerializer,
    AffiliationAccessGrantSerializer,
    AffiliationAccessRevokeSerializer,
    AffiliationReconfirmResponseSerializer,
)

# -----------------------------------------------------------------------------
# 시간대 상수
# -----------------------------------------------------------------------------
TIMEZONE_NAME = "Asia/Seoul"         # 서비스 레이어에 전달할 시간대 이름


def _require_json_content_type(request: HttpRequest) -> JsonResponse | None:
    """민감한 JSON 쓰기 요청이 브라우저 form 인코딩으로 제출되는 것을 차단합니다."""

    media_type = (getattr(request, "content_type", "") or "").split(";", 1)[0].strip().lower()
    if media_type == "application/json" or media_type.endswith("+json"):
        return None
    return JsonResponse({"error": "unsupported_media_type"}, status=415)


def _invalid_access_request(details: object) -> JsonResponse:
    """접근 API의 잘못된 JSON body를 같은 오류 형태로 반환합니다."""

    return JsonResponse(
        {
            "error": "invalid_request",
            "details": details,
        },
        status=400,
    )


def _invalid_access_query(details: object) -> JsonResponse:
    """접근 API의 잘못된 query를 같은 오류 형태로 반환합니다."""

    return JsonResponse(
        {
            "error": "invalid_query",
            "details": details,
        },
        status=400,
    )


# =============================================================================
# 1) 사용자: 내 소속 확인/변경 신청
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationView(APIView):
    """현재 사용자의 user_sdwt_prod 소속 변경을 신청합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """로그인 사용자 기준 소속 개요 데이터를 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 소속 개요 데이터

        부작용:
        - 없음

        오류:
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/account/affiliation

        예시 응답:
        - 예시 응답: 200 {"currentUserSdwtProd": "...", "accessibleUserSdwtProds": [...]}

        snake/camel 호환:
        - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        payload = services.get_affiliation_overview(user=user, timezone_name=TIMEZONE_NAME)
        return JsonResponse(payload)

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """소속 변경 요청을 생성합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 변경 요청 결과

        부작용:
        - 변경 요청 생성(서비스 레이어)

        오류:
        - 400: 입력 오류
        - 401: 미인증

        예시 요청:
        - 예시 요청: POST /api/v1/account/affiliation
        요청 바디 예시: {"userSdwtProd":"SDWT_A"}
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) JSON 바디 파싱
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) 입력 계약 검증
        # -----------------------------------------------------------------------------
        serializer = AffiliationChangeRequestSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)
        new_value = serializer.validated_data["userSdwtProd"]

        # -----------------------------------------------------------------------------
        # 4) 소속 옵션 유효성 검증
        # -----------------------------------------------------------------------------
        option = selectors.get_affiliation_option_by_user_sdwt_prod(user_sdwt_prod=new_value)
        if option is None:
            return JsonResponse({"error": "Invalid user_sdwt_prod"}, status=400)

        # -----------------------------------------------------------------------------
        # 5) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        response_payload, status_code = services.request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod=new_value,
            effective_from=None,
            timezone_name=TIMEZONE_NAME,
        )
        return JsonResponse(response_payload, status=status_code)


# =============================================================================
# 2) 사용자: 계정 화면 한 번에 로딩할 개요
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountOverviewView(APIView):
    """계정 화면에서 필요한 데이터를 한번에 제공합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """계정 화면 구성에 필요한 데이터를 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 계정 개요 데이터

        부작용:
        - 없음

        오류:
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/account/overview

        예시 응답:
        - 예시 응답: 200 {"user": {...}, "affiliationHistory": [...], "manageableGroups": [...]}

        snake/camel 호환:
        - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        payload = services.get_account_overview(user=user, timezone_name=TIMEZONE_NAME)
        return JsonResponse(payload)


@method_decorator(csrf_exempt, name="dispatch")
class AccountAccessRequestView(APIView):
    """현재 사용자의 포털/앱 접근 신청을 생성합니다."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """요청한 scope의 접근 신청을 pending 상태로 저장합니다."""

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        content_type_error = _require_json_content_type(request)
        if content_type_error is not None:
            return content_type_error

        body = parse_json_body(request)
        if body is None:
            return _invalid_access_request(
                {"body": ["유효한 JSON 객체가 필요합니다."]}
            )

        serializer = AccessRequestSerializer(data=body)
        if not serializer.is_valid():
            return _invalid_access_request(serializer.errors)

        payload, status_code = services.request_access(
            user=user,
            scope_keys=serializer.validated_data["scopes"],
        )
        return JsonResponse(payload, status=status_code)


# =============================================================================
# 3) Portal 관리자: 전체 scope 접근 권한 운영 관리
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountAccessUserView(APIView):
    """Portal 관리자가 scope별 전체 사용자의 최종 접근 상태를 조회합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """사용자별 최종 접근 상태 목록을 반환합니다."""

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        serializer = AccessUserQuerySerializer(data=request.GET)
        if not serializer.is_valid():
            return _invalid_access_query(serializer.errors)
        validated = serializer.validated_data
        payload, status_code = services.get_access_users(
            actor=user,
            request=request,
            scope_key=(validated.get("scope") or "").strip() or None,
            status=(validated.get("status") or "").strip() or None,
            source=(validated.get("source") or "").strip() or None,
            search=(validated.get("search") or "").strip() or None,
            department=(validated.get("department") or "").strip() or None,
            page=validated["page"],
            page_size=validated["pageSize"],
        )
        return JsonResponse(payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AccountAccessMatrixView(APIView):
    """Portal admin이 사용자별 전체 scope 접근 권한 매트릭스를 조회합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """Portal·활성 하위 scope와 사용자별 최종 접근 상태를 반환합니다."""

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        serializer = AccessMatrixQuerySerializer(data=request.GET)
        if not serializer.is_valid():
            return _invalid_access_query(serializer.errors)
        validated = serializer.validated_data
        payload, status_code = services.get_access_matrix(
            actor=user,
            request=request,
            search=(validated.get("search") or "").strip() or None,
            department=(validated.get("department") or "").strip() or None,
            manual_grant_only=validated["manualGrantOnly"],
            page=validated["page"],
            page_size=validated["pageSize"],
        )
        return JsonResponse(payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AccountAccessUserDecisionView(APIView):
    """Portal 관리자가 특정 사용자의 scope 접근 상태를 변경합니다."""

    def post(self, request: HttpRequest, user_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """사용자 접근 상태 변경 요청을 처리합니다."""

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        content_type_error = _require_json_content_type(request)
        if content_type_error is not None:
            return content_type_error

        body = parse_json_body(request)
        if body is None:
            return _invalid_access_request(
                {"body": ["유효한 JSON 객체가 필요합니다."]}
            )

        serializer = AccessUserDecisionSerializer(data=body)
        if not serializer.is_valid():
            return _invalid_access_request(serializer.errors)

        validated = serializer.validated_data
        payload, status_code = services.decide_user_access(
            actor=user,
            request=request,
            user_id=user_id,
            scope_key=validated["scope"],
            action=validated["action"],
            reason=validated.get("reason"),
            role=validated.get("role"),
            approve_all_apps=validated.get("approveAllApps", False),
        )
        return JsonResponse(payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AccountAccessUserDataScopeView(APIView):
    """Portal 관리자가 사용자의 앱별 소속 데이터 범위를 조회하고 변경합니다."""

    def get(
        self,
        request: HttpRequest,
        user_id: int,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """`?scope=emails`에 해당하는 현재·명시·전체 소속 범위를 반환합니다."""

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        serializer = UserScopeAffiliationDataQuerySerializer(data=request.GET)
        if not serializer.is_valid():
            return _invalid_access_query(serializer.errors)
        payload, status_code = services.get_user_scope_affiliation_data(
            actor=user,
            request=request,
            user_id=user_id,
            scope_key=serializer.validated_data["scope"],
        )
        return JsonResponse(payload, status=status_code)

    def put(
        self,
        request: HttpRequest,
        user_id: int,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """앱별 전체 모드와 명시 소속 목록을 원자적으로 교체합니다.

        요청 예시:
        `{"scope":"emails","dataScopeMode":"default","affiliationIds":[1,2]}`
        """

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        content_type_error = _require_json_content_type(request)
        if content_type_error is not None:
            return content_type_error
        body = parse_json_body(request)
        if body is None:
            return _invalid_access_request(
                {"body": ["유효한 JSON 객체가 필요합니다."]}
            )
        serializer = UserScopeAffiliationDataUpdateSerializer(data=body)
        if not serializer.is_valid():
            return _invalid_access_request(serializer.errors)
        validated = serializer.validated_data
        payload, status_code = services.update_user_scope_affiliation_data(
            actor=user,
            request=request,
            user_id=user_id,
            scope_key=validated["scope"],
            data_scope_mode=validated["dataScopeMode"],
            affiliation_ids=validated["affiliationIds"],
            reason=validated.get("reason"),
        )
        return JsonResponse(payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AccountAccessUserApplyAllView(APIView):
    """Portal 관리자가 한 사용자의 모든 활성 권한을 같은 값으로 변경합니다."""

    def post(self, request: HttpRequest, user_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """`{"value": "admin"}`을 받아 모든 매트릭스 권한에 적용합니다."""

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        content_type_error = _require_json_content_type(request)
        if content_type_error is not None:
            return content_type_error

        body = parse_json_body(request)
        if body is None:
            return _invalid_access_request(
                {"body": ["유효한 JSON 객체가 필요합니다."]}
            )

        serializer = ApplyAllUserAccessSerializer(data=body)
        if not serializer.is_valid():
            return _invalid_access_request(serializer.errors)

        payload, status_code = services.apply_all_user_accesses(
            actor=user,
            request=request,
            user_id=user_id,
            value=serializer.validated_data["value"],
            reason=serializer.validated_data["reason"],
        )
        return JsonResponse(payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AccountPendingAccessRequestView(APIView):
    """Portal 관리자가 전체 scope의 승인 대기 요청을 조회합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """전체 또는 선택한 scope의 승인 대기 요청을 반환합니다."""

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        serializer = PendingAccessRequestQuerySerializer(data=request.GET)
        if not serializer.is_valid():
            return _invalid_access_query(serializer.errors)
        validated = serializer.validated_data
        payload, status_code = services.get_pending_access_requests(
            actor=user,
            request=request,
            scope_key=(validated.get("scope") or "").strip() or None,
            page=validated["page"],
            page_size=validated["pageSize"],
        )
        return JsonResponse(payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AccountPendingAccessRequestBulkApproveView(APIView):
    """Portal 관리자가 선택한 승인 대기 요청을 일괄 승인합니다."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """선택한 요청을 일반 사용자 역할로 각각 승인합니다."""

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        content_type_error = _require_json_content_type(request)
        if content_type_error is not None:
            return content_type_error

        body = parse_json_body(request)
        if body is None:
            return _invalid_access_request(
                {"body": ["유효한 JSON 객체가 필요합니다."]}
            )

        serializer = BulkApprovePendingAccessRequestSerializer(data=body)
        if not serializer.is_valid():
            return _invalid_access_request(serializer.errors)
        payload, status_code = services.approve_pending_access_requests(
            actor=user,
            request=request,
            request_ids=serializer.validated_data["requestIds"],
        )
        return JsonResponse(payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AccountAccessPolicyRuleCollectionView(APIView):
    """Portal 관리자가 scope별 접근 정책 규칙 목록을 조회하고 생성합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """접근 정책 규칙 목록을 반환합니다."""

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        serializer = AccessPolicyRuleQuerySerializer(data=request.GET)
        if not serializer.is_valid():
            return _invalid_access_query(serializer.errors)
        validated = serializer.validated_data

        payload, status_code = services.get_access_policy_rules(
            actor=user,
            request=request,
            scope_key=(validated.get("scope") or "").strip() or None,
        )
        return JsonResponse(payload, status=status_code)

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """접근 정책 규칙을 생성합니다."""

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        content_type_error = _require_json_content_type(request)
        if content_type_error is not None:
            return content_type_error

        body = parse_json_body(request)
        if body is None:
            return _invalid_access_request(
                {"body": ["유효한 JSON 객체가 필요합니다."]}
            )

        serializer = AccessPolicyRuleCreateSerializer(data=body)
        if not serializer.is_valid():
            return _invalid_access_request(serializer.errors)

        validated = serializer.validated_data
        payload, status_code = services.create_access_policy_rule(
            actor=user,
            request=request,
            scope_key=validated["scope"],
            rule_type=validated["ruleType"],
            value=validated["value"],
            is_active=validated.get("isActive"),
        )
        return JsonResponse(payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AccountAccessPolicyRuleBulkApplyView(APIView):
    """Portal 관리자가 한 부서의 자동 접근 규칙을 여러 scope에 적용합니다."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """`{"value":"개발팀","scopeKeys":["portal","appstore"],"isActive":true}`를 처리합니다."""

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        content_type_error = _require_json_content_type(request)
        if content_type_error is not None:
            return content_type_error

        body = parse_json_body(request)
        if body is None:
            return _invalid_access_request(
                {"body": ["유효한 JSON 객체가 필요합니다."]}
            )

        serializer = BulkApplyAccessPolicyRuleSerializer(data=body)
        if not serializer.is_valid():
            return _invalid_access_request(serializer.errors)

        validated = serializer.validated_data
        payload, status_code = services.bulk_apply_access_policy_rules(
            actor=user,
            request=request,
            scope_keys=validated["scopeKeys"],
            value=validated["value"],
            is_active=validated["isActive"],
        )
        return JsonResponse(payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AccountAccessPolicyRuleDetailView(APIView):
    """Portal 관리자가 특정 접근 정책 규칙을 수정하거나 삭제합니다."""

    def patch(self, request: HttpRequest, rule_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """접근 정책 규칙을 수정합니다."""

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        content_type_error = _require_json_content_type(request)
        if content_type_error is not None:
            return content_type_error

        body = parse_json_body(request)
        if body is None:
            return _invalid_access_request(
                {"body": ["유효한 JSON 객체가 필요합니다."]}
            )

        serializer = AccessPolicyRuleUpdateSerializer(data=body)
        if not serializer.is_valid():
            return _invalid_access_request(serializer.errors)

        validated = serializer.validated_data
        payload, status_code = services.update_access_policy_rule(
            actor=user,
            request=request,
            rule_id=rule_id,
            rule_type=validated.get("ruleType") if "ruleType" in validated else None,
            value=validated.get("value") if "value" in validated else None,
            is_active=validated.get("isActive") if "isActive" in validated else None,
        )
        return JsonResponse(payload, status=status_code)

    def delete(self, request: HttpRequest, rule_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """접근 정책 규칙을 삭제합니다."""

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        payload, status_code = services.delete_access_policy_rule(
            actor=user,
            request=request,
            rule_id=rule_id,
        )
        return JsonResponse(payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AccountAccessAuditLogView(APIView):
    """Portal admin이 전체 또는 선택한 scope의 접근 권한 감사 로그를 조회합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """접근 권한 변경 이력 목록을 반환합니다."""

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        serializer = AccessAuditLogQuerySerializer(data=request.GET)
        if not serializer.is_valid():
            return _invalid_access_query(serializer.errors)
        validated = serializer.validated_data
        payload, status_code = services.get_access_audit_logs(
            actor=user,
            request=request,
            scope_key=(validated.get("scope") or "").strip() or None,
            user_id=validated.get("userId"),
            action=(validated.get("action") or "").strip() or None,
            page=validated["page"],
            page_size=validated["pageSize"],
        )
        return JsonResponse(payload, status=status_code)


# =============================================================================
# 4) 소속 manager/특권 사용자: 소속 변경 요청 승인/거절
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationApprovalView(APIView):
    """해당 소속 manager가 소속 변경 요청을 처리합니다."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """소속 변경 요청을 승인/거절합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 승인/거절 결과

        부작용:
        - 변경 요청 승인/거절 처리

        오류:
        - 400: 입력 오류
        - 401: 미인증

        예시 요청:
        - 예시 요청: POST /api/v1/account/affiliation/approve
          요청 바디 예시: {"changeId":123,"decision":"approve"}
          요청 바디 예시: {"changeId":123,"decision":"reject","rejectionReason":"소속 정보 불일치"}

        입력 계약:
        - changeId, decision, rejectionReason
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) JSON 바디 파싱
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) 입력 검증
        # -----------------------------------------------------------------------------
        serializer = AffiliationApprovalSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        change_id = serializer.validated_data["changeId"]
        decision = (serializer.validated_data.get("decision") or "approve").lower()
        rejection_reason = (serializer.validated_data.get("rejectionReason") or "").strip() or None

        # -----------------------------------------------------------------------------
        # 4) 의사결정에 따른 서비스 호출
        # -----------------------------------------------------------------------------
        if decision == "reject":
            response_payload, status_code = services.reject_affiliation_change(
                approver=user,
                change_id=change_id,
                rejection_reason=rejection_reason,
            )
        else:
            response_payload, status_code = services.approve_affiliation_change(
                approver=user,
                change_id=change_id,
            )
        return JsonResponse(response_payload, status=status_code)


# =============================================================================
# 5) 관리자/사용자: 소속 변경 요청 목록 조회 (검색/필터/페이지네이션)
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationRequestListView(APIView):
    """소속 변경 요청 목록을 조회합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """소속 변경 요청 목록을 검색/필터링하여 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 변경 요청 목록 및 페이지 정보

        부작용:
        - 없음

        오류:
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/account/affiliation/requests?status=pending&search=kim&userSdwtProd=SDWT_A&page=2&pageSize=50
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) query 계약 검증
        # -----------------------------------------------------------------------------
        serializer = AffiliationRequestQuerySerializer(data=request.GET)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)
        validated = serializer.validated_data
        status = validated["status"]

        # -----------------------------------------------------------------------------
        # 3) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        payload, status_code = services.get_affiliation_change_requests(
            user=user,
            status=status if status and status.lower() != "all" else None,
            search=(validated.get("search") or "").strip() or None,
            user_sdwt_prod=(validated.get("userSdwtProd") or "").strip() or None,
            page=validated["page"],
            page_size=validated["pageSize"],
        )
        return JsonResponse(payload, status=status_code)


# =============================================================================
# 6) 사용자: 외부 예측 소속 변경 시 "재확인" 상태 조회/응답
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationReconfirmView(APIView):
    """외부 예측 소속 변경 시 사용자 재확인 여부를 조회/응답합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """재확인 대상 여부와 관련 정보를 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 재확인 상태 정보

        부작용:
        - 없음

        오류:
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/account/affiliation/reconfirm

        snake/camel 호환:
        - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        payload = services.get_affiliation_reconfirm_status(user=user)
        return JsonResponse(payload)

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """사용자가 재확인 응답을 제출합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 처리 결과

        부작용:
        - 자동 승인 선택 시 소속 변경이 즉시 적용됨
        - 예측값 불일치 또는 예측 없음 선택 시 승인 대기 요청이 생성됨
        - 기존 유지/자동 승인/승인 대기 생성 성공 시 재확인 플래그가 해제됨

        오류:
        - 400: 입력 오류
        - 401: 미인증
        - 409: 재확인 대상 아님

        예시 요청:
        - 예시 요청: POST /api/v1/account/affiliation/reconfirm
          요청 바디 예시(변경 적용): {"accepted": true, "userSdwtProd": "G1"}
        - 예시 요청: POST /api/v1/account/affiliation/reconfirm
          요청 바디 예시(승인 대기): {"accepted": true, "userSdwtProd": "G2"}
        - 예시 요청: POST /api/v1/account/affiliation/reconfirm
          요청 바디 예시(기존 유지): {"accepted": false}

        표기 계약:
        - 요청 바디는 camelCase만 허용
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) JSON 바디 파싱
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) 입력 검증
        # -----------------------------------------------------------------------------
        serializer = AffiliationReconfirmResponseSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        # -----------------------------------------------------------------------------
        # 4) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        validated = serializer.validated_data
        response_payload, status_code = services.submit_affiliation_reconfirm_response(
            user=user,
            accepted=validated["accepted"],
            user_sdwt_prod=validated.get("user_sdwt_prod"),
            timezone_name=TIMEZONE_NAME,
        )
        return JsonResponse(response_payload, status=status_code)


# =============================================================================
# 8) 소속 멤버 목록 조회
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationMembersView(APIView):
    """접근 가능한 소속의 사용자 멤버 목록을 조회합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """소속 멤버 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 소속 멤버 목록

        부작용:
        - 없음

        오류:
        - 400: 소속 식별자 누락
        - 401: 미인증
        - 403: 접근 권한 없음

        예시 요청:
        - 예시 요청: GET /api/v1/account/affiliation/members?userSdwtProd=SDWT_A

        입력 계약:
        - userSdwtProd
        """

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        serializer = AffiliationMembersQuerySerializer(data=request.GET)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)
        user_sdwt_prod = serializer.validated_data["userSdwtProd"]
        payload, status_code = services.get_affiliation_members(
            user=user,
            user_sdwt_prod=user_sdwt_prod,
        )
        return JsonResponse(payload, status=status_code)


# =============================================================================
# 9) manager: 소속 접근 역할 부여·변경·회수
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationAccessView(APIView):
    """manager가 담당 소속의 사용자 접근 역할을 관리합니다."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """사용자에게 소속 역할을 부여하거나 기존 역할을 변경합니다.

        예시 요청:
        - POST /api/v1/account/affiliation/access
        - {"userId": 12, "userSdwtProd": "GROUP-A", "role": "member"}
        """

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        content_type_error = _require_json_content_type(request)
        if content_type_error is not None:
            return content_type_error
        body = parse_json_body(request)
        if body is None:
            return _invalid_access_request(
                {"body": ["유효한 JSON 객체가 필요합니다."]}
            )

        serializer = AffiliationAccessGrantSerializer(data=body)
        if not serializer.is_valid():
            return _invalid_access_request(serializer.errors)
        validated = serializer.validated_data
        target_user = selectors.get_user_by_id(user_id=validated["userId"])
        if target_user is None:
            return JsonResponse({"error": "User not found"}, status=404)

        payload, status_code = services.grant_or_revoke_access(
            grantor=user,
            target_group=validated["userSdwtProd"],
            target_user=target_user,
            action="grant",
            role=validated["role"],
            reason=validated["reason"],
        )
        return JsonResponse(payload, status=status_code)

    def delete(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """사용자의 추가 소속 접근 역할을 회수합니다.

        예시 요청:
        - DELETE /api/v1/account/affiliation/access
        - {"userId": 12, "userSdwtProd": "GROUP-A"}
        """

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        content_type_error = _require_json_content_type(request)
        if content_type_error is not None:
            return content_type_error
        body = parse_json_body(request)
        if body is None:
            return _invalid_access_request(
                {"body": ["유효한 JSON 객체가 필요합니다."]}
            )

        serializer = AffiliationAccessRevokeSerializer(data=body)
        if not serializer.is_valid():
            return _invalid_access_request(serializer.errors)
        validated = serializer.validated_data
        target_user = selectors.get_user_by_id(user_id=validated["userId"])
        if target_user is None:
            return JsonResponse({"error": "User not found"}, status=404)

        payload, status_code = services.grant_or_revoke_access(
            grantor=user,
            target_group=validated["userSdwtProd"],
            target_user=target_user,
            action="revoke",
            role=None,
            reason=validated["reason"],
        )
        return JsonResponse(payload, status=status_code)


from .user_pool import AccountUserPoolView, LineSdwtOptionsView
from .external_sync import AccountExternalAffiliationSyncView
