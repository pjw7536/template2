# =============================================================================
# 모듈 설명: 활동 로그 직렬화 유틸을 제공합니다.
# - 주요 대상: Activity query/body 스키마, serialize_activity_log
# - 불변 조건: API 응답에서 내부 브리지 IP는 제외합니다.
# =============================================================================
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rest_framework import serializers

from .models import ActivityLog

INTERNAL_BRIDGE_REMOTE_ADDR = "172.18.0.1"
MAX_APP_ID_LENGTH = 120
MAX_APP_NAME_LENGTH = 160
MAX_SOURCE_NAME_LENGTH = 80
MAX_PASTED_TEXT_LENGTH = 200_000


class StrictSerializer(serializers.Serializer):
    """선언되지 않은 query와 body 필드를 거절합니다."""

    def to_internal_value(self, data):
        """알 수 없는 필드가 조용히 무시되지 않게 검사합니다."""

        if isinstance(data, Mapping):
            unexpected_fields = sorted(set(data) - set(self.fields))
            if unexpected_fields:
                raise serializers.ValidationError(
                    {"unexpectedFields": unexpected_fields}
                )
        return super().to_internal_value(data)


class StrictTextField(serializers.CharField):
    """JSON의 문자열 필드가 숫자를 문자열로 암묵적 변환하지 않게 합니다."""

    default_error_messages = {"invalid": "문자열이어야 합니다."}

    def to_internal_value(self, data):
        """문자열 타입을 확인한 뒤 기본 문자열 검증을 수행합니다."""

        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class ActivityLogQuerySerializer(StrictSerializer):
    """최근 활동 로그 query 스키마."""

    limit = serializers.IntegerField(required=False, default=50, min_value=1, max_value=200)


class AppAccessEventSerializer(StrictSerializer):
    """앱 접속 이벤트 body 스키마."""

    appId = StrictTextField(max_length=MAX_APP_ID_LENGTH, trim_whitespace=True)
    appName = StrictTextField(max_length=MAX_APP_NAME_LENGTH, trim_whitespace=True)
    path = StrictTextField(max_length=512, required=False, default="", allow_blank=True)


class AppAccessStatsQuerySerializer(StrictSerializer):
    """앱 접속 통계 query 스키마."""

    to = serializers.CharField(max_length=10, required=False, allow_blank=True)
    appId = serializers.CharField(max_length=MAX_APP_ID_LENGTH, required=False, allow_blank=True)
    period = serializers.ChoiceField(
        choices=["", "day", "week", "month"],
        required=False,
        allow_blank=True,
    )

    def get_fields(self):
        """Python 예약어인 from query 필드를 명시적으로 추가합니다."""

        fields = super().get_fields()
        fields["from"] = serializers.CharField(
            max_length=10,
            required=False,
            allow_blank=True,
        )
        return fields


class ManualAppAccessStatsSerializer(StrictSerializer):
    """외부 앱 수동 접속 통계 body 스키마."""

    pastedText = StrictTextField(max_length=MAX_PASTED_TEXT_LENGTH, trim_whitespace=False)
    sourceName = StrictTextField(
        max_length=MAX_SOURCE_NAME_LENGTH,
        required=False,
        default="manual",
        allow_blank=True,
        trim_whitespace=True,
    )

    def validate_sourceName(self, value):  # noqa: N802 - HTTP camelCase 계약
        """빈 출처 이름을 기존 기본값인 manual로 정규화합니다."""

        return value or "manual"

    def validate_pastedText(self, value):
        """공백만 있는 붙여넣기 원문을 거절하고 원본은 보존합니다."""

        if not value.strip():
            raise serializers.ValidationError("하나 이상의 데이터 행이 필요합니다.")
        return value


def _serialize_metadata(metadata: Any) -> Any:
    """응답에 노출할 ActivityLog metadata를 정리합니다."""

    normalized_metadata = metadata or {}
    if (
        isinstance(normalized_metadata, dict)
        and normalized_metadata.get("remote_addr") == INTERNAL_BRIDGE_REMOTE_ADDR
    ):
        # 도커 브리지 내부 IP는 의미가 없으므로 응답에서 제외합니다.
        return {
            key: value
            for key, value in normalized_metadata.items()
            if key != "remote_addr"
        }

    return normalized_metadata


def serialize_activity_log(entry: ActivityLog) -> dict[str, Any]:
    """ActivityLog 모델을 API 응답 형식으로 직렬화합니다.

    입력:
    - entry: ActivityLog 인스턴스

    반환:
    - dict[str, Any]: 활동 로그 API 응답 dict

    부작용:
    - 없음(읽기 전용 변환)

    오류:
    - 없음
    """

    user = entry.user
    username = user.get_username() if user else None

    return {
        "id": entry.id,
        "user": username,
        "action": entry.action,
        "path": entry.path,
        "method": entry.method,
        "status": entry.status_code,
        "metadata": _serialize_metadata(entry.metadata),
        "timestamp": entry.created_at.isoformat(),
    }


__all__ = [
    "ActivityLogQuerySerializer",
    "AppAccessEventSerializer",
    "AppAccessStatsQuerySerializer",
    "ManualAppAccessStatsSerializer",
    "serialize_activity_log",
]
