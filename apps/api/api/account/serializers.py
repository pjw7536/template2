from __future__ import annotations

from rest_framework import serializers


class ExternalAffiliationRecordSerializer(serializers.Serializer):
    """외부 DB에서 전달되는 사용자 예측 소속 레코드 입력 스키마."""

    knox_id = serializers.CharField(max_length=150)
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

