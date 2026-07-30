# =============================================================================
# 모듈 설명: account 도메인 요청/응답 스키마를 정의합니다.
# - 주요 대상: 외부 소속 동기화, 소속 재확인/승인 입력 스키마
# - 불변 조건: 필드명은 클라이언트 계약과 호환되어야 합니다.
# =============================================================================

"""계정 도메인 요청/응답 스키마 정의 모음.

- 주요 대상: 외부 소속 동기화, 소속 재확인/승인 입력 스키마
- 주요 엔드포인트/클래스: ExternalAffiliationSyncSerializer 등
- 가정/불변 조건: 필드명은 클라이언트 계약에 맞춰 유지됨
"""
from __future__ import annotations

from collections.abc import Mapping

from rest_framework import serializers

from .models import (
    AccessAuditLog,
    AccessPolicyRule,
    AccessRole,
    AccessSource,
    UserAccess,
    UserSdwtProdAccess,
)


class ExternalAffiliationRecordSerializer(serializers.Serializer):
    """외부 DB에서 전달되는 사용자 예측 소속 레코드 입력 스키마."""

    knox_id = serializers.CharField(max_length=150)
    username = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    department = serializers.CharField(max_length=128)
    user_sdwt_prod = serializers.CharField(max_length=64)
    source_updated_at = serializers.DateTimeField(required=False, allow_null=True)


class ExternalAffiliationSyncSerializer(serializers.Serializer):
    """외부 예측 소속 동기화 요청 스키마."""

    records = ExternalAffiliationRecordSerializer(many=True)


class AffiliationReconfirmResponseSerializer(serializers.Serializer):
    """소속 재확인 응답 입력 스키마."""

    accepted = serializers.BooleanField()
    department = serializers.CharField(max_length=128, required=False, allow_blank=True)
    line = serializers.CharField(max_length=64, required=False, allow_blank=True)
    user_sdwt_prod = serializers.CharField(max_length=64, required=False, allow_blank=True)


class AffiliationApprovalSerializer(serializers.Serializer):
    """소속 변경 승인/거절 입력 스키마."""

    changeId = serializers.IntegerField()
    decision = serializers.ChoiceField(choices=["approve", "reject"], required=False)
    rejectionReason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class StrictAccessSerializer(serializers.Serializer):
    """접근 API에 선언되지 않은 입력 필드가 들어오면 명시적으로 거절합니다."""

    def to_internal_value(self, data):
        """선언되지 않은 필드가 조용히 무시되지 않게 검사합니다."""

        if isinstance(data, Mapping):
            unexpected_fields = sorted(set(data) - set(self.fields))
            if unexpected_fields:
                raise serializers.ValidationError(
                    {"unexpectedFields": unexpected_fields}
                )
        return super().to_internal_value(data)


class AffiliationAccessGrantSerializer(StrictAccessSerializer):
    """소속 접근 역할 부여·변경 입력 스키마."""

    userId = serializers.IntegerField(min_value=1)
    userSdwtProd = serializers.CharField(max_length=64, trim_whitespace=True)
    role = serializers.ChoiceField(choices=UserSdwtProdAccess.Roles.values)
    reason = serializers.CharField(max_length=500, allow_blank=False)


class AffiliationAccessRevokeSerializer(StrictAccessSerializer):
    """소속 접근 역할 회수 입력 스키마."""

    userId = serializers.IntegerField(min_value=1)
    userSdwtProd = serializers.CharField(max_length=64, trim_whitespace=True)
    reason = serializers.CharField(max_length=500, allow_blank=False)


class AccessRequestSerializer(StrictAccessSerializer):
    """현재 사용자 접근 신청 입력 스키마."""

    scopes = serializers.ListField(
        child=serializers.CharField(max_length=64),
        allow_empty=False,
        max_length=20,
    )

    def validate_scopes(self, values):
        """scope key를 입력 순서대로 중복 제거합니다."""

        normalized = list(
            dict.fromkeys(value.strip() for value in values if value.strip())
        )
        if not normalized:
            raise serializers.ValidationError("하나 이상의 scope가 필요합니다.")
        return normalized


class AccessUserDecisionSerializer(StrictAccessSerializer):
    """관리자 사용자별 접근 상태 변경 입력 스키마."""

    scope = serializers.CharField(max_length=64)
    action = serializers.ChoiceField(
        choices=["approve", "reject", "grant", "revoke", "reset_to_policy", "change_role"]
    )
    role = serializers.ChoiceField(choices=AccessRole.values, required=False, allow_blank=True, allow_null=True)
    approveAllApps = serializers.BooleanField(required=False, default=False)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        """권한 변경 action별 필수 입력을 검증합니다."""

        action = attrs.get("action")
        role = attrs.get("role")
        if action == "change_role" and not role:
            raise serializers.ValidationError({"role": "change_role에는 role이 필요합니다."})
        if role and action not in {"approve", "grant", "change_role"}:
            raise serializers.ValidationError(
                {"role": f"{action}에는 role을 사용할 수 없습니다."}
            )
        if attrs.get("approveAllApps") and not (
            attrs.get("scope") == "portal" and action == "approve"
        ):
            raise serializers.ValidationError(
                {
                    "approveAllApps": (
                        "portal scope의 approve에서만 사용할 수 있습니다."
                    )
                }
            )
        if action in {"grant", "revoke", "change_role", "reset_to_policy"} and not (
            attrs.get("reason") or ""
        ).strip():
            raise serializers.ValidationError(
                {"reason": "수동 권한 변경 사유가 필요합니다."}
            )
        return attrs


class UserScopeAffiliationDataQuerySerializer(StrictAccessSerializer):
    """사용자별 앱 소속 데이터 범위 조회 query 스키마."""

    scope = serializers.CharField(max_length=64)


class UserScopeAffiliationDataUpdateSerializer(StrictAccessSerializer):
    """사용자별 앱 소속 데이터 범위 전체 교체 입력 스키마."""

    scope = serializers.CharField(max_length=64)
    dataScopeMode = serializers.ChoiceField(choices=UserAccess.DataScopeModes.values)
    affiliationIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
        max_length=500,
    )
    reason = serializers.CharField(
        max_length=500,
        required=True,
        allow_blank=False,
        allow_null=False,
    )

    def validate_affiliationIds(self, values):
        """소속 ID를 입력 순서대로 중복 제거합니다."""

        return list(dict.fromkeys(values))

    def validate(self, attrs):
        """모든 소속 데이터 범위 변경에 추적 가능한 사유를 요구합니다."""

        if not (attrs.get("reason") or "").strip():
            raise serializers.ValidationError(
                {"reason": "소속 데이터 범위 변경 사유가 필요합니다."}
            )
        return attrs


class AccessPaginationQuerySerializer(StrictAccessSerializer):
    """접근 관리 목록의 공통 페이지 query 스키마."""

    page = serializers.IntegerField(required=False, default=1, min_value=1)
    pageSize = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)


class AccessUserQuerySerializer(AccessPaginationQuerySerializer):
    """scope별 사용자 접근 목록 query 스키마."""

    scope = serializers.CharField(max_length=64, required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=["", "all", "allowed", "pending", "denied", "not_requested", "inactive"],
        required=False,
        default="",
        allow_blank=True,
    )
    source = serializers.ChoiceField(
        choices=["", "all", *AccessSource.values],
        required=False,
        default="",
        allow_blank=True,
    )
    search = serializers.CharField(max_length=150, required=False, allow_blank=True)
    department = serializers.CharField(max_length=128, required=False, allow_blank=True)

    def validate_status(self, value):
        """전체 상태 sentinel을 selector가 사용하는 빈 필터로 정규화합니다."""

        return "" if value == "all" else value

    def validate_source(self, value):
        """전체 출처 sentinel을 selector가 사용하는 빈 필터로 정규화합니다."""

        return "" if value == "all" else value


class PendingAccessRequestQuerySerializer(AccessPaginationQuerySerializer):
    """전체 또는 scope별 승인 대기 요청 목록 query 스키마."""

    scope = serializers.CharField(max_length=64, required=False, allow_blank=True)

    def validate_scope(self, value):
        """전체 범위 sentinel을 빈 scope 필터로 정규화합니다."""

        return "" if value == "all" else value.strip()


class BulkApprovePendingAccessRequestSerializer(StrictAccessSerializer):
    """선택한 승인 대기 요청의 일괄 승인 입력 스키마."""

    requestIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=100,
    )

    def validate_requestIds(self, values):
        """요청 ID를 입력 순서대로 중복 제거합니다."""

        return list(dict.fromkeys(values))


class ApplyAllUserAccessSerializer(StrictAccessSerializer):
    """한 사용자의 모든 활성 scope에 동일한 권한을 적용하는 입력 스키마."""

    value = serializers.ChoiceField(
        choices=("inherit", "user", "admin", "denied"),
    )
    reason = serializers.CharField(max_length=500, allow_blank=False)


class AccessMatrixQuerySerializer(AccessPaginationQuerySerializer):
    """사용자별 전체 scope 매트릭스 query 스키마."""

    search = serializers.CharField(max_length=150, required=False, allow_blank=True)
    department = serializers.CharField(max_length=128, required=False, allow_blank=True)
    manualGrantOnly = serializers.BooleanField(required=False, default=False)


class AccessPolicyRuleQuerySerializer(StrictAccessSerializer):
    """정책 규칙 목록 query 스키마."""

    scope = serializers.CharField(max_length=64, required=False, allow_blank=True)


class AccessAuditLogQuerySerializer(AccessPaginationQuerySerializer):
    """접근 감사 로그 목록 query 스키마."""

    scope = serializers.CharField(max_length=64, required=False, allow_blank=True)
    userId = serializers.IntegerField(required=False, min_value=1)
    action = serializers.ChoiceField(
        choices=["", "all", *AccessAuditLog.Actions.values],
        required=False,
        default="",
        allow_blank=True,
    )

    def validate_scope(self, value):
        """전체 scope sentinel을 감사 selector의 빈 필터로 정규화합니다."""

        return "" if value.casefold() == "all" else value

    def validate_action(self, value):
        """전체 action sentinel을 감사 selector의 빈 필터로 정규화합니다."""

        return "" if value == "all" else value


class AccessPolicyRuleCreateSerializer(StrictAccessSerializer):
    """관리자 부서 접근 정책 규칙 생성 입력 스키마."""

    scope = serializers.CharField(max_length=64)
    ruleType = serializers.ChoiceField(choices=AccessPolicyRule.RuleTypes.values)
    value = serializers.CharField(max_length=150, allow_blank=True)
    isActive = serializers.BooleanField(required=False)


class BulkApplyAccessPolicyRuleSerializer(StrictAccessSerializer):
    """부서 자동 접근 규칙을 여러 scope에 일괄 적용하는 입력 스키마."""

    value = serializers.CharField(max_length=150, allow_blank=True)
    scopeKeys = serializers.ListField(
        child=serializers.CharField(max_length=64),
        allow_empty=False,
        max_length=100,
    )
    isActive = serializers.BooleanField()

    def validate_scopeKeys(self, values):
        """scope key를 입력 순서대로 중복 제거합니다."""

        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class AccessPolicyRuleUpdateSerializer(StrictAccessSerializer):
    """관리자 부서 접근 정책 규칙 수정 입력 스키마."""

    ruleType = serializers.ChoiceField(choices=AccessPolicyRule.RuleTypes.values, required=False)
    value = serializers.CharField(max_length=150, required=False, allow_blank=True)
    isActive = serializers.BooleanField(required=False)

    def validate(self, attrs):
        """수정할 필드가 하나 이상 있는지 검증합니다."""

        if not attrs:
            raise serializers.ValidationError(
                {"nonFieldErrors": "수정할 필드가 필요합니다."}
            )
        return attrs
