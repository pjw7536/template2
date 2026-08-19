# =============================================================================
# 모듈: 드론 직렬화 유틸
# 주요 함수: serialize_early_inform_entry
# 주요 가정: 응답 키는 camelCase로 반환합니다.
# =============================================================================
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Sequence

from rest_framework import serializers

from .models import (
    DroneEarlyInform,
    DroneSopNeedToSendRule,
    DroneSopTarget,
    DroneSopTargetChannelConfig,
)

MAX_FIELD_LENGTH = 50
MAX_TARGET_FIELD_LENGTH = 64
LINE_DASHBOARD_ASSISTANT_MAX_RANGE_DAYS = 31
LINE_DASHBOARD_ASSISTANT_FILTER_MODES = {
    "target_user_sdwt_prod",
    "user_sdwt_prod",
    "sdwt_prod",
}


def serialize_drone_sop_target_configuration(
    target: DroneSopTarget | None,
) -> dict[str, object]:
    """normalized channel/rule row에서 target 설정 응답을 생성합니다."""

    configs = list(target.channel_configs.all()) if target is not None else []
    config_by_channel = {config.channel: config for config in configs}
    jira = config_by_channel.get(DroneSopTargetChannelConfig.Channels.JIRA)
    messenger = config_by_channel.get(DroneSopTargetChannelConfig.Channels.MESSENGER)
    mail = config_by_channel.get(DroneSopTargetChannelConfig.Channels.MAIL)
    rule = None
    if target is not None:
        try:
            rule = target.needtosend_rule
        except DroneSopNeedToSendRule.DoesNotExist:
            rule = None
    return {
        "jiraKey": jira.jira_project_key if jira else None,
        "jiraTemplateKey": jira.template_key if jira else None,
        "messengerTemplateKey": messenger.template_key if messenger else None,
        "mailTemplateKey": mail.template_key if mail else None,
        "jiraEnabled": bool(jira.enabled) if jira else True,
        "messengerEnabled": bool(messenger.enabled) if messenger else True,
        "messengerForceNewChatroom": bool(messenger.force_new_chatroom) if messenger else False,
        "mailEnabled": bool(mail.enabled) if mail else True,
        "needtosendCommentLastAt": rule.comment_keyword if rule else None,
        "needtosendEnabled": bool(rule.enabled) if rule else False,
        "needtosendIgnoreSampleType": bool(rule.ignore_sample_type) if rule else False,
    }


def normalize_line_dashboard_assistant_date_range(
    *,
    from_value: str,
    to_value: str,
) -> tuple[date, date]:
    """ESOP Assistant 조회 기간을 날짜로 변환하고 최대 31일로 제한합니다."""

    start_date = date.fromisoformat(from_value)
    end_date = date.fromisoformat(to_value)
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    earliest = end_date - timedelta(days=LINE_DASHBOARD_ASSISTANT_MAX_RANGE_DAYS - 1)
    return max(start_date, earliest), end_date


def normalize_line_dashboard_assistant_options(
    *,
    line_id: Any,
    view: str,
    from_value: str,
    to_value: str,
    line_filter_mode: str | None,
    recent_hours_start: int | None,
    recent_hours_end: int | None,
    current_time: Any,
) -> tuple[str, date, date, tuple[Any, Any] | None]:
    """ESOP Assistant 조회 옵션을 검증하고 최근 시간 범위를 계산합니다."""

    if view not in {"status", "history"}:
        raise ValueError("지원하지 않는 ESOP 화면 종류입니다.")
    normalized_line_id = line_id.strip() if isinstance(line_id, str) else ""
    if not normalized_line_id:
        raise ValueError("ESOP line ID가 필요합니다.")
    start_date, end_date = normalize_line_dashboard_assistant_date_range(
        from_value=from_value,
        to_value=to_value,
    )
    if view == "history":
        return normalized_line_id, start_date, end_date, None
    if line_filter_mode not in LINE_DASHBOARD_ASSISTANT_FILTER_MODES:
        raise ValueError("지원하지 않는 ESOP line 필터 모드입니다.")
    if (
        type(recent_hours_start) is not int
        or type(recent_hours_end) is not int
        or not 0 <= recent_hours_end <= recent_hours_start <= 168
    ):
        raise ValueError("ESOP 최근 시간 범위가 올바르지 않습니다.")
    recent_range = (
        current_time - timedelta(hours=recent_hours_start),
        current_time - timedelta(hours=recent_hours_end) + timedelta(minutes=5),
    )
    return normalized_line_id, start_date, end_date, recent_range


def serialize_line_dashboard_assistant_snapshot(
    *,
    view: str,
    line_id: str,
    start_date: date,
    end_date: date,
    generated_at: Any,
    total_count: int,
    status_rows: Sequence[dict[str, Any]],
    daily_rows: Sequence[dict[str, Any]],
    recent_rows: Sequence[dict[str, Any]],
    line_filter_mode: str | None,
    recent_hours_start: int | None,
    recent_hours_end: int | None,
) -> dict[str, object]:
    """ESOP Assistant 집계 row를 개인정보가 제외된 camelCase 응답으로 변환합니다."""

    snapshot: dict[str, object] = {
        "view": view,
        "lineId": line_id,
        "from": start_date.isoformat(),
        "to": end_date.isoformat(),
        "generatedAt": generated_at.isoformat(),
        "totalCount": total_count,
        "statusCounts": [
            {
                "status": str(row["status"] or "Unspecified"),
                "count": int(row["count"] or 0),
            }
            for row in status_rows
        ],
        "dailyCounts": [
            {
                "date": row["day"].isoformat() if row["day"] else None,
                "count": int(row["count"] or 0),
                "needToSendCount": int(row["need_to_send_count"] or 0),
                "instantInformCount": int(row["instant_inform_count"] or 0),
            }
            for row in daily_rows
        ],
        "recentRows": [
            {
                "id": row["id"],
                "createdAt": row["created_at"].isoformat(),
                "lineId": row["line_id"],
                "status": row["status"],
                "eqpId": row["eqp_id"],
                "chamberIds": row["chamber_ids"],
                "lotId": row["lot_id"],
                "mainStep": row["main_step"],
                "sampleType": row["sample_type"],
                "needToSend": row["needtosend"],
                "instantInform": row["instant_inform"],
            }
            for row in recent_rows
        ],
    }
    if view == "status":
        snapshot.update(
            {
                "lineFilterMode": line_filter_mode,
                "recentHoursStart": recent_hours_start,
                "recentHoursEnd": recent_hours_end,
            }
        )
    return snapshot


class DroneRequestValidationError(ValueError):
    """Drone API 요청 검증 실패를 표현하는 예외입니다."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        """응답 상태 코드와 메시지를 함께 보관합니다."""

        super().__init__(message)
        self.status_code = status_code


def normalize_short_text(
    value: Any,
    *,
    allow_non_str: bool = False,
    max_length: int = MAX_FIELD_LENGTH,
) -> str | None:
    """짧은 문자열 필드를 공백 제거와 길이 제한 기준으로 정규화합니다."""

    if isinstance(value, str):
        trimmed = value.strip()
    elif value is None:
        trimmed = ""
    elif allow_non_str:
        trimmed = str(value).strip()
    else:
        return None

    if not trimmed:
        return None
    return trimmed if len(trimmed) <= max_length else None


def normalize_text(value: Any, *, allow_non_str: bool = False) -> str | None:
    """문자열 값을 공백 제거 기준으로 정규화합니다."""

    if value is None:
        return None
    if not isinstance(value, str):
        if not allow_non_str:
            return None
        value = str(value)
    trimmed = value.strip()
    return trimmed if trimmed else None


def normalize_text_list(values: Sequence[Any], *, allow_non_str: bool = False) -> list[str]:
    """문자열 리스트를 공백 제거 기준으로 정규화합니다."""

    normalized: list[str] = []
    for value in values:
        cleaned = normalize_text(value, allow_non_str=allow_non_str)
        if cleaned:
            normalized.append(cleaned)
    return normalized


def normalize_lookup_text(value: Any, *, allow_non_str: bool = False) -> str | None:
    """대소문자 비구분 비교용 문자열 키를 정규화합니다."""

    cleaned = normalize_text(value, allow_non_str=allow_non_str)
    return cleaned.casefold() if cleaned else None


def normalize_lookup_text_list(values: Sequence[Any], *, allow_non_str: bool = False) -> list[str]:
    """대소문자 비구분 비교용 문자열 키 리스트를 정규화합니다."""

    normalized: list[str] = []
    for value in values:
        cleaned = normalize_lookup_text(value, allow_non_str=allow_non_str)
        if cleaned:
            normalized.append(cleaned)
    return normalized


def normalize_chatroom_id(value: Any) -> int | None:
    """채팅룸 ID 값을 양의 정수로 정규화합니다."""

    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def display_delivery_target(value: Any) -> str | None:
    """내부 marker target을 화면용 target 라벨로 변환합니다."""

    target = normalize_text(value)
    if target and target.startswith("__"):
        return "Target 미지정"
    return target


def collapse_display_values(values: Sequence[Any]) -> list[str]:
    """표시값을 유지하면서 대소문자 비구분 중복을 제거합니다."""

    display_by_key: dict[str, str] = {}
    for value in values:
        normalized = normalize_text(value)
        if not normalized:
            continue
        display_by_key.setdefault(normalized.casefold(), normalized)
    return sorted(display_by_key.values())


def normalize_line_id(value: Any) -> str:
    """lineId 값을 공백 제거 기준으로 정규화합니다."""

    normalized = normalize_short_text(value)
    return normalized or ""


def normalize_main_step(value: Any) -> str | None:
    """mainStep 값을 공백 제거와 길이 제한 기준으로 정규화합니다."""

    return normalize_short_text(value, allow_non_str=True)


def normalize_target_text(value: Any) -> str:
    """target/user SDWT 계열 문자열을 공백 제거 기준으로 정규화합니다."""

    return value.strip() if isinstance(value, str) else ""


def normalize_custom_end_step(value: Any) -> str | None:
    """customEndStep 값을 빈 문자열은 None으로 처리해 정규화합니다."""

    if value is None:
        return None
    trimmed = value.strip() if isinstance(value, str) else str(value).strip()
    if not trimmed:
        return None
    if len(trimmed) > MAX_FIELD_LENGTH:
        raise DroneRequestValidationError("customEndStep must be 50 characters or fewer")
    return trimmed


def normalize_updated_by(value: Any) -> str | None:
    """updated_by 값을 공백 제거와 길이 제한 기준으로 정규화합니다."""

    return normalize_short_text(value)


def parse_limit_param(*, body_value: Any, query_value: Any) -> int | None:
    """JSON 바디와 쿼리 파라미터에서 limit 값을 파싱합니다."""

    raw_limit = body_value if body_value is not None else query_value
    if raw_limit is None:
        return None

    try:
        limit = int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise DroneRequestValidationError("limit must be an integer") from exc

    return limit if limit > 0 else None


def parse_positive_int(value: Any, *, error_message: str = "A valid id is required") -> int:
    """양의 정수 입력 값을 파싱합니다."""

    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise DroneRequestValidationError(error_message) from exc
    if parsed <= 0:
        raise DroneRequestValidationError(error_message)
    return parsed


def parse_user_id_list(value: Any) -> list[int]:
    """userIds 값을 중복 제거된 양의 정수 리스트로 파싱합니다."""

    if not isinstance(value, list):
        raise DroneRequestValidationError("userIds must be a list")

    user_ids: list[int] = []
    seen: set[int] = set()
    for item in value:
        if isinstance(item, bool):
            raise DroneRequestValidationError("userIds must contain only integers")
        if isinstance(item, int):
            user_id = item
        elif isinstance(item, str):
            try:
                user_id = int(item.strip())
            except ValueError as exc:
                raise DroneRequestValidationError("userIds must contain only integers") from exc
        else:
            raise DroneRequestValidationError("userIds must contain only integers")

        if user_id <= 0:
            raise DroneRequestValidationError("userIds must contain only positive integers")
        if user_id in seen:
            continue
        seen.add(user_id)
        user_ids.append(user_id)
    return user_ids


def parse_external_knox_id_list(value: Any) -> list[str]:
    """externalKnoxIds 값을 중복 제거된 문자열 리스트로 파싱합니다."""

    if value is None:
        return []
    if not isinstance(value, list):
        raise DroneRequestValidationError("externalKnoxIds must be a list")

    knox_ids: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise DroneRequestValidationError("externalKnoxIds must contain only strings")
        knox_id = item.strip().lower()
        if not knox_id:
            raise DroneRequestValidationError("externalKnoxIds must contain non-empty strings")
        if knox_id in seen:
            continue
        seen.add(knox_id)
        knox_ids.append(knox_id)
    return knox_ids


def parse_optional_comment(payload: dict[str, Any]) -> str | None:
    """즉시 인폼 요청의 comment 필드를 파싱합니다."""

    raw_comment = payload.get("comment")
    if raw_comment is not None and not isinstance(raw_comment, str):
        raise DroneRequestValidationError("comment must be a string")
    return raw_comment.strip() if isinstance(raw_comment, str) else None


def parse_required_channel(payload: dict[str, Any]) -> str:
    """채널 재시도 요청의 channel 필드를 파싱합니다."""

    raw_channel = payload.get("channel")
    if not isinstance(raw_channel, str):
        raise DroneRequestValidationError("channel must be a string")
    channel = raw_channel.strip().lower()
    if not channel:
        raise DroneRequestValidationError("channel is required")
    return channel


def parse_optional_text_field(
    payload: dict[str, Any],
    *,
    field_name: str,
    max_length: int,
) -> tuple[bool, str | None]:
    """옵션 문자열 필드의 제공 여부와 정규화 값을 반환합니다."""

    if field_name not in payload:
        return False, None

    raw_value = payload.get(field_name)
    if raw_value is not None and not isinstance(raw_value, str):
        raise DroneRequestValidationError(f"{field_name} must be a string or null")

    normalized = raw_value.strip() if isinstance(raw_value, str) else ""
    if normalized and len(normalized) > max_length:
        raise DroneRequestValidationError(f"{field_name} must be {max_length} characters or fewer")
    return True, normalized or None


def parse_optional_bool_field(
    payload: dict[str, Any],
    *,
    field_name: str,
) -> tuple[bool, bool | None]:
    """옵션 boolean 필드의 제공 여부와 값을 반환합니다."""

    if field_name not in payload:
        return False, None
    raw_value = payload.get(field_name)
    if not isinstance(raw_value, bool):
        raise DroneRequestValidationError(f"{field_name} must be a boolean")
    return True, raw_value


class DroneEarlyInformCreateSerializer(serializers.Serializer):
    """Drone 조기 알림 생성 입력을 기존 API 오류 계약에 맞춰 검증합니다."""

    lineId = serializers.JSONField(required=False, allow_null=True)
    mainStep = serializers.JSONField(required=False, allow_null=True)
    customEndStep = serializers.JSONField(required=False, allow_null=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """생성 필수값과 선택 종료 단계를 service 입력 형태로 정규화합니다."""

        line_id = normalize_line_id(attrs.get("lineId"))
        if not line_id:
            raise serializers.ValidationError("lineId is required")

        main_step = normalize_main_step(attrs.get("mainStep"))
        if not main_step:
            raise serializers.ValidationError("mainStep is required")

        try:
            custom_end_step = normalize_custom_end_step(attrs.get("customEndStep"))
        except DroneRequestValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc

        attrs["normalized_line_id"] = line_id
        attrs["normalized_main_step"] = main_step
        attrs["normalized_custom_end_step"] = custom_end_step
        return attrs


class DroneEarlyInformUpdateFieldsSerializer(serializers.Serializer):
    """Drone 조기 알림 PATCH의 선택 변경 필드를 검증합니다."""

    lineId = serializers.JSONField(required=False, allow_null=True)
    mainStep = serializers.JSONField(required=False, allow_null=True)
    customEndStep = serializers.JSONField(required=False, allow_null=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """제공된 camelCase 필드만 service용 snake_case 변경값으로 변환합니다."""

        updates: dict[str, Any] = {}
        if "lineId" in attrs:
            line_id = normalize_line_id(attrs.get("lineId"))
            if not line_id:
                raise serializers.ValidationError("lineId is required")
            updates["line_id"] = line_id

        if "mainStep" in attrs:
            main_step = normalize_main_step(attrs.get("mainStep"))
            if not main_step:
                raise serializers.ValidationError("mainStep is required")
            updates["main_step"] = main_step

        if "customEndStep" in attrs:
            try:
                updates["custom_end_step"] = normalize_custom_end_step(
                    attrs.get("customEndStep")
                )
            except DroneRequestValidationError as exc:
                raise serializers.ValidationError(str(exc)) from exc

        if not updates:
            raise serializers.ValidationError("No valid fields to update")
        attrs["normalized_updates"] = updates
        return attrs


class _DroneNotificationTargetMappingFieldsSerializer(serializers.Serializer):
    """Drone 알림 target mapping의 공통 식별 필드를 검증합니다."""

    lineId = serializers.JSONField(required=False, allow_null=True)
    targetUserSdwtProd = serializers.JSONField(required=False, allow_null=True)
    sdwtProd = serializers.JSONField(required=False, allow_null=True)
    userSdwtProd = serializers.JSONField(required=False, allow_null=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """공통 camelCase 필드를 기존 오류 순서대로 정규화합니다."""

        normalized_fields = {
            "normalized_line_id": normalize_line_id(attrs.get("lineId")),
            "normalized_target_user_sdwt_prod": normalize_target_text(
                attrs.get("targetUserSdwtProd")
            ),
            "normalized_sdwt_prod": normalize_target_text(attrs.get("sdwtProd")),
            "normalized_user_sdwt_prod": normalize_target_text(
                attrs.get("userSdwtProd")
            ),
        }
        required_fields = (
            ("normalized_line_id", "lineId is required"),
            (
                "normalized_target_user_sdwt_prod",
                "targetUserSdwtProd is required",
            ),
            ("normalized_sdwt_prod", "sdwtProd is required"),
            ("normalized_user_sdwt_prod", "userSdwtProd is required"),
        )
        for field_name, error_message in required_fields:
            if not normalized_fields[field_name]:
                raise serializers.ValidationError(error_message)

        attrs.update(normalized_fields)
        return attrs


class DroneNotificationTargetMappingCreateSerializer(
    _DroneNotificationTargetMappingFieldsSerializer
):
    """Drone 알림 target mapping 생성 입력을 검증합니다."""

    needtosendWithoutComment = serializers.JSONField(required=False, allow_null=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """생성 시 Comment 생략 정책의 기본값을 False로 적용합니다."""

        attrs = super().validate(attrs)
        value = attrs.get("needtosendWithoutComment", False)
        if not isinstance(value, bool):
            raise serializers.ValidationError(
                "needtosendWithoutComment must be bool"
            )
        attrs["normalized_needtosend_without_comment"] = value
        return attrs


class DroneNotificationTargetMappingUpdateSerializer(
    _DroneNotificationTargetMappingFieldsSerializer
):
    """Drone 알림 target mapping 예약 정책 수정 입력을 검증합니다."""

    needtosendWithoutComment = serializers.JSONField(required=False, allow_null=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """수정 시 Comment 생략 정책 boolean을 필수로 검증합니다."""

        attrs = super().validate(attrs)
        value = attrs.get("needtosendWithoutComment")
        if not isinstance(value, bool):
            raise serializers.ValidationError(
                "needtosendWithoutComment must be bool"
            )
        attrs["normalized_needtosend_without_comment"] = value
        return attrs


class DroneNotificationTargetMappingDeleteSerializer(
    _DroneNotificationTargetMappingFieldsSerializer
):
    """Drone 알림 target mapping 삭제 식별 입력을 검증합니다."""


class _DroneSopTargetAdminWriteSerializer(serializers.Serializer):
    """Drone SOP target 생성·수정 공통 입력을 검증합니다."""

    lineId = serializers.JSONField(required=False)
    targetUserSdwtProd = serializers.JSONField(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """필수 문자열을 기존 관리자 API 오류 계약에 맞춰 정규화합니다."""

        raw_line_id = attrs.get("lineId")
        if not isinstance(raw_line_id, str) or not raw_line_id.strip():
            raise serializers.ValidationError("lineId is required")
        line_id = raw_line_id.strip()
        if len(line_id) > MAX_FIELD_LENGTH:
            raise serializers.ValidationError("lineId must be 50 characters or fewer")

        target_user_sdwt_prod = normalize_target_text(attrs.get("targetUserSdwtProd"))
        if not target_user_sdwt_prod:
            raise serializers.ValidationError("targetUserSdwtProd is required")
        if len(target_user_sdwt_prod) > MAX_TARGET_FIELD_LENGTH:
            raise serializers.ValidationError(
                "targetUserSdwtProd must be 64 characters or fewer"
            )

        attrs["lineId"] = line_id
        attrs["targetUserSdwtProd"] = target_user_sdwt_prod
        return attrs


class DroneSopTargetAdminCreateSerializer(_DroneSopTargetAdminWriteSerializer):
    """Drone SOP target 관리자 생성 입력 스키마입니다."""


class DroneSopTargetAdminUpdateSerializer(_DroneSopTargetAdminWriteSerializer):
    """Drone SOP target 관리자 수정 입력 스키마입니다."""

    id = serializers.JSONField(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """target ID와 수정 필드를 함께 검증합니다."""

        try:
            attrs["id"] = parse_positive_int(
                attrs.get("id"),
                error_message="id is required",
            )
        except DroneRequestValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return super().validate(attrs)


class DroneSopTargetAdminDeleteSerializer(serializers.Serializer):
    """Drone SOP target 관리자 삭제 입력 스키마입니다."""

    id = serializers.JSONField(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """삭제 대상 ID를 양의 정수로 정규화합니다."""

        try:
            attrs["id"] = parse_positive_int(
                attrs.get("id"),
                error_message="id is required",
            )
        except DroneRequestValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return attrs


def serialize_early_inform_entry(entry: DroneEarlyInform) -> dict[str, Any]:
    """DroneEarlyInform 모델을 API 응답 형태로 직렬화합니다.

    인자:
        entry: DroneEarlyInform 인스턴스.

    반환:
        직렬화된 dict.

    부작용:
        없음. 읽기 전용 변환입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 업데이트 시각 정규화
    # -----------------------------------------------------------------------------
    updated_at = entry.updated_at
    return {
        "id": int(entry.id),
        "lineId": entry.line_id,
        "mainStep": entry.main_step,
        "customEndStep": entry.custom_end_step,
        "updatedBy": entry.updated_by,
        "updatedAt": updated_at.isoformat() if hasattr(updated_at, "isoformat") and updated_at else None,
    }
