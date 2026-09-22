# =============================================================================
# 모듈 설명: Observer 대용량 조회 query를 검증합니다.
# - 주요 클래스: ObserverLogPageQuerySerializer, ObserverEvidenceLogQuerySerializer
# - 불변 조건: cursor는 요청 범위와 log type이 일치해야 합니다.
# =============================================================================

"""Observer 조회 요청 serializer."""

from __future__ import annotations

import base64
from datetime import datetime
import json
from typing import Any

from rest_framework import serializers

from .services import MAX_OBSERVER_QUERY_DAYS, normalize_observer_datetime

DEFAULT_OBSERVER_PAGE_SIZE = 250
MAX_OBSERVER_PAGE_SIZE = 1000
OBSERVER_LOG_TYPES = (
    "eqp",
    "tip",
    "spc-interlock",
    "fdc-interlock",
    "ctttm",
    "racb",
    "esop",
)


def _normalize_id(value: object) -> str:
    """Observer 식별자를 공백 제거 후 대문자로 정규화합니다."""

    return str(value or "").strip().upper()


def _parse_boundary(value: str, *, is_end: bool) -> datetime:
    """날짜 또는 datetime 문자열을 Asia/Seoul aware 값으로 변환합니다."""

    try:
        return normalize_observer_datetime(value, is_end=is_end)
    except ValueError as exc:
        raise serializers.ValidationError(
            "올바른 날짜 또는 datetime 형식이어야 합니다."
        ) from exc


def encode_observer_cursor(payload: dict[str, Any]) -> str:
    """페이지 경계를 외부 구조에 의존하지 않는 URL-safe cursor로 인코딩합니다."""

    serialized = json.dumps(
        {"v": 1, **payload},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(serialized).decode("ascii").rstrip("=")


def decode_observer_cursor(value: str) -> dict[str, Any]:
    """URL-safe cursor를 검증 가능한 payload로 디코딩합니다."""

    raw_value = str(value or "").strip()
    if not raw_value:
        raise serializers.ValidationError("cursor 값이 비어 있습니다.")

    try:
        padding = "=" * (-len(raw_value) % 4)
        decoded = base64.urlsafe_b64decode(f"{raw_value}{padding}".encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise serializers.ValidationError("cursor 형식이 올바르지 않습니다.") from exc

    if not isinstance(payload, dict) or payload.get("v") != 1:
        raise serializers.ValidationError("지원하지 않는 cursor 버전입니다.")
    if "eventTime" not in payload or "tieBreaker" not in payload:
        raise serializers.ValidationError("cursor 페이지 경계가 누락되었습니다.")
    return payload


class ObserverLogPageQuerySerializer(serializers.Serializer):
    """Observer paged log 조회 query를 검증합니다."""

    eqpId = serializers.CharField(max_length=100)
    from_value = serializers.CharField(max_length=64)
    to = serializers.CharField(max_length=64)
    pageSize = serializers.IntegerField(
        required=False,
        default=DEFAULT_OBSERVER_PAGE_SIZE,
        min_value=1,
        max_value=MAX_OBSERVER_PAGE_SIZE,
    )
    cursor = serializers.CharField(required=False, allow_blank=False, max_length=2048)
    types = serializers.CharField(required=False, allow_blank=False, max_length=200)

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        """HTTP 예약어와 겹치는 from query를 내부 필드명으로 옮깁니다."""

        mutable_data = data.copy()
        mutable_data["from_value"] = data.get("from")
        return super().to_internal_value(mutable_data)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """날짜 범위, log type, cursor scope를 함께 검증합니다."""

        start_at = _parse_boundary(attrs["from_value"], is_end=False)
        end_at = _parse_boundary(attrs["to"], is_end=True)
        if start_at > end_at:
            raise serializers.ValidationError(
                {"from": "from은 to보다 늦을 수 없습니다."}
            )
        if (end_at - start_at).days >= MAX_OBSERVER_QUERY_DAYS:
            raise serializers.ValidationError(
                {"from": f"조회 기간은 최대 {MAX_OBSERVER_QUERY_DAYS}일입니다."}
            )

        eqp_id = _normalize_id(attrs["eqpId"])
        if not eqp_id:
            raise serializers.ValidationError({"eqpId": "eqpId가 필요합니다."})

        raw_types = attrs.get("types")
        requested_types = (
            [item.strip().lower() for item in raw_types.split(",") if item.strip()]
            if raw_types
            else list(OBSERVER_LOG_TYPES)
        )
        invalid_types = [
            item for item in requested_types if item not in OBSERVER_LOG_TYPES
        ]
        if invalid_types:
            raise serializers.ValidationError(
                {"types": f"지원하지 않는 log type입니다: {', '.join(invalid_types)}"}
            )
        requested_types = list(dict.fromkeys(requested_types))

        attrs["eqp_id"] = eqp_id
        attrs["start_at"] = start_at.isoformat()
        attrs["end_at"] = end_at.isoformat()
        attrs["log_types"] = requested_types
        attrs["range_key"] = f"{start_at.isoformat()}:{end_at.isoformat()}"

        raw_cursor = attrs.get("cursor")
        if raw_cursor:
            payload = decode_observer_cursor(raw_cursor)
            expected_type = str(self.context.get("log_type") or "").strip().lower()
            if (
                payload.get("eqpId") != eqp_id
                or payload.get("range") != attrs["range_key"]
                or payload.get("logType") != expected_type
            ):
                raise serializers.ValidationError(
                    {"cursor": "cursor와 현재 조회 범위가 일치하지 않습니다."}
                )
            attrs["cursor_payload"] = payload
        else:
            attrs["cursor_payload"] = None

        return attrs

class ObserverLogDetailQuerySerializer(serializers.Serializer):
    """Observer log detail 조회 query를 검증합니다."""

    eqpId = serializers.CharField(max_length=100)
    logId = serializers.CharField(max_length=500)

    def validate_eqpId(self, value: str) -> str:
        """설비 ID를 Observer 공통 규칙으로 정규화합니다."""

        normalized = _normalize_id(value)
        if not normalized:
            raise serializers.ValidationError("eqpId가 필요합니다.")
        return normalized

    def validate_logId(self, value: str) -> str:
        """상세 log ID의 공백 입력을 거절합니다."""

        normalized = str(value or "").strip()
        if not normalized:
            raise serializers.ValidationError("logId가 필요합니다.")
        return normalized


class ObserverEvidenceLogQuerySerializer(serializers.Serializer):
    """AI 분석 근거 단건 복원 query를 검증합니다."""

    eqpId = serializers.CharField(max_length=100)
    evidenceId = serializers.CharField(max_length=1000)
    from_value = serializers.CharField(max_length=64)
    to = serializers.CharField(max_length=64)

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        """HTTP `from` query를 Python 내부 필드로 옮깁니다."""

        mutable_data = data.copy()
        mutable_data["from_value"] = data.get("from")
        return super().to_internal_value(mutable_data)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """설비, evidence ID, 분석 날짜 범위를 정규화합니다."""

        start_at = _parse_boundary(attrs["from_value"], is_end=False)
        end_at = _parse_boundary(attrs["to"], is_end=True)
        if start_at > end_at:
            raise serializers.ValidationError(
                {"from": "from은 to보다 늦을 수 없습니다."}
            )
        if (end_at - start_at).days >= MAX_OBSERVER_QUERY_DAYS:
            raise serializers.ValidationError(
                {"from": f"조회 기간은 최대 {MAX_OBSERVER_QUERY_DAYS}일입니다."}
            )

        eqp_id = _normalize_id(attrs["eqpId"])
        evidence_id = str(attrs["evidenceId"] or "").strip()
        if not eqp_id:
            raise serializers.ValidationError({"eqpId": "eqpId가 필요합니다."})
        if not evidence_id:
            raise serializers.ValidationError(
                {"evidenceId": "evidenceId가 필요합니다."}
            )

        attrs["eqp_id"] = eqp_id
        attrs["evidence_id"] = evidence_id
        attrs["start_at"] = start_at.isoformat()
        attrs["end_at"] = end_at.isoformat()
        return attrs
