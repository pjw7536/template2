"""L3 Spider 제외 필터와 mail rule의 변경·발송을 처리합니다."""

from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime as dt_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo

import pandas as pd
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from api.common.services import send_knox_mail_api
from api.l3_spider import selectors

from . import line_name_rules
from .analytics import _normalize_display_status
from .metadata import _matches_pattern, _parallel_read, _read_mail_event_file
from .state import (
    L3SpiderServiceError,
    MAIL_SEVERITY_STATUSES,
    _MAIL_DIGEST_PREVIEW_LIMIT,
    _meta_cache,
    _stats_cache,
    _structure_cache,
)

def _require_user_id(user: Any) -> int:
    """인증 사용자 ID를 반환하고 없으면 권한 오류를 발생시킵니다."""

    user_id = getattr(user, "id", None)
    if not user_id:
        raise L3SpiderServiceError("Authentication required", status_code=401)
    return int(user_id)


def _serialize_exclusion_filter(row) -> dict[str, object]:
    """제외 필터 모델을 API 응답 형태로 변환합니다."""

    created_by = None
    if row.created_by:
        created_by = row.created_by.get_full_name() or row.created_by.username

    return {
        "id": row.id,
        "lineId": row.line_id,
        "processId": row.process_id,
        "edsStep": row.eds_step,
        "stepSeq": row.step_seq,
        "ppid": row.ppid,
        "eqpch": row.eqpch,
        "binName": row.bin_name,
        "dateTo": row.date_to.isoformat() if row.date_to else None,
        "isActive": row.is_active,
        "memo": row.memo,
        "createdBy": created_by,
        "createdAt": row.created_at.strftime("%Y-%m-%d %H:%M"),
        "updatedAt": row.updated_at.strftime("%Y-%m-%d %H:%M"),
    }


def list_exclusion_filters(*, user: Any) -> list[dict[str, object]]:
    """요청 사용자가 소유한 제외 필터 목록을 최신 등록순으로 조회합니다."""

    from ..models import L3SpiderExclusionFilter

    user_id = _require_user_id(user)
    filters = L3SpiderExclusionFilter.objects.select_related("created_by").filter(
        created_by_id=user_id,
    )
    return [_serialize_exclusion_filter(row) for row in filters]


def create_exclusion_filter(data: dict[str, object], *, user) -> dict[str, int]:
    """제외 필터를 생성하고 관련 캐시를 무효화합니다."""

    from ..models import L3SpiderExclusionFilter

    user_id = _require_user_id(user)
    row = L3SpiderExclusionFilter.objects.create(
        line_id=data["line_id"],
        process_id=data["process_id"],
        eds_step=data["eds_step"],
        step_seq=data["step_seq"],
        ppid=data["ppid"],
        eqpch=data["eqpch"],
        bin_name=data["bin_name"],
        date_from=data.get("date_from"),
        date_to=data.get("date_to"),
        is_active=data["is_active"],
        memo=data.get("memo", ""),
        created_by_id=user_id,
    )
    invalidate_exclusion_cache()
    return {"id": row.id}


def update_exclusion_filter(
    filter_id: int,
    data: dict[str, object],
    *,
    user: Any,
) -> dict[str, int]:
    """사용자 소유 제외 필터를 부분 수정하고 관련 캐시를 무효화합니다."""

    from ..models import L3SpiderExclusionFilter

    user_id = _require_user_id(user)
    try:
        row = L3SpiderExclusionFilter.objects.get(pk=filter_id, created_by_id=user_id)
    except L3SpiderExclusionFilter.DoesNotExist as exc:
        raise L3SpiderServiceError("Not found", status_code=404) from exc

    field_map = {
        "line_id": "line_id",
        "process_id": "process_id",
        "eds_step": "eds_step",
        "step_seq": "step_seq",
        "ppid": "ppid",
        "eqpch": "eqpch",
        "bin_name": "bin_name",
        "date_from": "date_from",
        "date_to": "date_to",
        "is_active": "is_active",
        "memo": "memo",
    }
    for source, target in field_map.items():
        if source in data:
            setattr(row, target, data[source])
    row.save()
    invalidate_exclusion_cache()
    return {"id": row.id}


def delete_exclusion_filter(filter_id: int, *, user: Any) -> None:
    """사용자 소유 제외 필터를 삭제하고 관련 캐시를 무효화합니다."""

    from ..models import L3SpiderExclusionFilter

    user_id = _require_user_id(user)
    try:
        row = L3SpiderExclusionFilter.objects.get(pk=filter_id, created_by_id=user_id)
    except L3SpiderExclusionFilter.DoesNotExist as exc:
        raise L3SpiderServiceError("Not found", status_code=404) from exc

    row.delete()
    invalidate_exclusion_cache()


def invalidate_exclusion_cache() -> None:
    """필터 변경 시 meta·stats·structure 캐시를 무효화합니다."""
    _meta_cache.clear()
    _stats_cache.clear()
    _structure_cache.clear()


def _display_user_name(user: Any) -> str:
    """사용자 표시 이름을 일관된 우선순위로 반환합니다."""

    if not user:
        return ""
    return (
        user.get_full_name()
        or getattr(user, "username", "")
        or getattr(user, "email", "")
        or getattr(user, "sabun", "")
        or str(user)
    )


def _display_user_email(user: Any) -> str:
    """사용자 email 표시값을 반환합니다."""

    return str(getattr(user, "email", "") or "").strip()


def _serialize_mail_rule_permission(row) -> dict[str, object]:
    """메일 rule 공유 권한 모델을 API 응답 형태로 변환합니다."""

    user = row.user
    return {
        "id": row.id,
        "userId": user.id,
        "user": _display_user_email(user) or getattr(user, "username", "") or getattr(user, "sabun", ""),
        "displayName": _display_user_name(user),
        "email": _display_user_email(user),
        "username": getattr(user, "username", "") or "",
        "sabun": getattr(user, "sabun", "") or "",
        "accessLevel": row.access_level,
        "createdAt": row.created_at.strftime("%Y-%m-%d %H:%M"),
        "updatedAt": row.updated_at.strftime("%Y-%m-%d %H:%M"),
    }


def _mail_rule_access(row, *, user_id: int) -> dict[str, object]:
    """현재 사용자의 rule 접근 권한을 계산합니다."""

    if row.created_by_id == user_id:
        return {
            "accessLevel": "owner",
            "isOwner": True,
            "canWrite": True,
            "canManage": True,
        }

    from ..models import L3SpiderMailRulePermission

    for permission in row.permissions.all():
        if permission.user_id != user_id:
            continue
        can_write = permission.access_level == L3SpiderMailRulePermission.AccessLevels.WRITE
        return {
            "accessLevel": permission.access_level,
            "isOwner": False,
            "canWrite": can_write,
            "canManage": False,
        }

    return {
        "accessLevel": None,
        "isOwner": False,
        "canWrite": False,
        "canManage": False,
    }


def _serialize_mail_rule(row, *, user_id: int | None = None) -> dict[str, object]:
    """메일 알림 규칙 모델을 API 응답 형태로 변환합니다."""

    created_by = row.created_by.get_full_name() or row.created_by.username
    access = _mail_rule_access(row, user_id=user_id) if user_id else {
        "accessLevel": "owner",
        "isOwner": True,
        "canWrite": True,
        "canManage": True,
    }
    permissions = []
    if access["canManage"]:
        permissions = [
            _serialize_mail_rule_permission(permission)
            for permission in row.permissions.all()
        ]

    return {
        "id": row.id,
        "name": row.name,
        "lineId": row.line_id,
        "processId": row.process_id,
        "edsStep": row.eds_step,
        "stepSeq": row.step_seq,
        "ppid": row.ppid,
        "eqpch": row.eqpch,
        "binName": row.bin_name,
        "dateTo": row.date_to.isoformat() if row.date_to else None,
        "severityMode": row.severity_mode,
        "receiverEmails": list(row.receiver_emails or []),
        "scheduleType": row.schedule_type,
        "sendTime": row.send_time.strftime("%H:%M") if row.send_time else "09:00",
        "timezone": row.timezone,
        "isActive": row.is_active,
        "memo": row.memo,
        "lastSentAt": row.last_sent_at.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M") if row.last_sent_at else None,
        "lastCheckedAt": row.last_checked_at.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M") if row.last_checked_at else None,
        "accessLevel": access["accessLevel"],
        "isOwner": access["isOwner"],
        "canWrite": access["canWrite"],
        "canManage": access["canManage"],
        "ownerName": _display_user_name(row.created_by),
        "ownerEmail": _display_user_email(row.created_by),
        "permissions": permissions,
        "createdBy": created_by,
        "createdAt": row.created_at.strftime("%Y-%m-%d %H:%M"),
        "updatedAt": row.updated_at.strftime("%Y-%m-%d %H:%M"),
    }


def list_mail_rules(*, user: Any) -> list[dict[str, object]]:
    """요청 사용자가 소유한 메일 알림 규칙 목록을 조회합니다."""

    user_id = _require_user_id(user)
    rules = selectors.list_mail_rules_for_user(user_id)
    return [_serialize_mail_rule(row, user_id=user_id) for row in rules]


def create_mail_rule(data: dict[str, object], *, user: Any) -> dict[str, int]:
    """메일 알림 규칙을 생성합니다."""

    from ..models import L3SpiderMailRule

    user_id = _require_user_id(user)
    row = L3SpiderMailRule.objects.create(
        name=data["name"],
        line_id=data["line_id"],
        process_id=data["process_id"],
        eds_step=data["eds_step"],
        step_seq=data["step_seq"],
        ppid=data["ppid"],
        eqpch=data["eqpch"],
        bin_name=data["bin_name"],
        date_to=data.get("date_to"),
        severity_mode=data["severity_mode"],
        receiver_emails=data["receiver_emails"],
        schedule_type=data["schedule_type"],
        send_time=data["send_time"],
        timezone=data["timezone"],
        is_active=data["is_active"],
        memo=data.get("memo", ""),
        created_by_id=user_id,
    )
    return {"id": row.id}


def update_mail_rule(
    rule_id: int,
    data: dict[str, object],
    *,
    user: Any,
) -> dict[str, int]:
    """사용자 소유 메일 알림 규칙을 부분 수정합니다."""

    from ..models import L3SpiderMailRule

    user_id = _require_user_id(user)
    try:
        row = selectors.get_mail_rule_for_user(rule_id=rule_id, user_id=user_id)
    except L3SpiderMailRule.DoesNotExist as exc:
        raise L3SpiderServiceError("Not found", status_code=404) from exc
    if not _mail_rule_access(row, user_id=user_id)["canWrite"]:
        raise L3SpiderServiceError("Write permission required", status_code=403)

    field_map = {
        "name": "name",
        "line_id": "line_id",
        "process_id": "process_id",
        "eds_step": "eds_step",
        "step_seq": "step_seq",
        "ppid": "ppid",
        "eqpch": "eqpch",
        "bin_name": "bin_name",
        "date_to": "date_to",
        "severity_mode": "severity_mode",
        "receiver_emails": "receiver_emails",
        "schedule_type": "schedule_type",
        "send_time": "send_time",
        "timezone": "timezone",
        "is_active": "is_active",
        "memo": "memo",
    }
    for source, target in field_map.items():
        if source in data:
            setattr(row, target, data[source])
    row.save()
    return {"id": row.id}


def delete_mail_rule(rule_id: int, *, user: Any) -> None:
    """사용자 소유 메일 알림 규칙을 삭제합니다."""

    from ..models import L3SpiderMailRule

    user_id = _require_user_id(user)
    try:
        row = selectors.get_owned_mail_rule_for_user(rule_id=rule_id, user_id=user_id)
    except L3SpiderMailRule.DoesNotExist as exc:
        raise L3SpiderServiceError("Not found", status_code=404) from exc
    row.delete()


def list_mail_rule_permissions(rule_id: int, *, user: Any) -> list[dict[str, object]]:
    """owner가 메일 rule 공유 권한 목록을 조회합니다."""

    from ..models import L3SpiderMailRule

    user_id = _require_user_id(user)
    try:
        selectors.get_owned_mail_rule_for_user(rule_id=rule_id, user_id=user_id)
    except L3SpiderMailRule.DoesNotExist as exc:
        raise L3SpiderServiceError("Not found", status_code=404) from exc
    return [
        _serialize_mail_rule_permission(permission)
        for permission in selectors.list_mail_rule_permissions(rule_id=rule_id)
    ]


def replace_mail_rule_permissions(
    rule_id: int,
    permissions: list[dict[str, str]],
    *,
    user: Any,
) -> dict[str, object]:
    """owner가 메일 rule 공유 권한 목록을 전체 교체합니다."""

    from ..models import L3SpiderMailRule, L3SpiderMailRulePermission

    user_id = _require_user_id(user)
    try:
        row = selectors.get_owned_mail_rule_for_user(rule_id=rule_id, user_id=user_id)
    except L3SpiderMailRule.DoesNotExist as exc:
        raise L3SpiderServiceError("Not found", status_code=404) from exc

    resolved: list[tuple[Any, str]] = []
    resolved_user_ids: set[int] = set()
    for item in permissions:
        target_user = selectors.find_user_for_mail_rule_permission(item["user"])
        if target_user is None:
            raise L3SpiderServiceError(
                f"사용자를 찾을 수 없습니다: {item['user']}",
                status_code=400,
            )
        if target_user.id == row.created_by_id:
            raise L3SpiderServiceError("owner는 별도 권한 항목으로 추가할 수 없습니다.", status_code=400)
        if target_user.id in resolved_user_ids:
            raise L3SpiderServiceError("같은 사용자를 중복 입력할 수 없습니다.", status_code=400)
        resolved_user_ids.add(target_user.id)
        resolved.append((target_user, item["access_level"]))

    with transaction.atomic():
        L3SpiderMailRulePermission.objects.filter(rule=row).delete()
        L3SpiderMailRulePermission.objects.bulk_create([
            L3SpiderMailRulePermission(
                rule=row,
                user=target_user,
                access_level=access_level,
                granted_by_id=user_id,
            )
            for target_user, access_level in resolved
        ])

    return {
        "id": row.id,
        "permissions": [
            _serialize_mail_rule_permission(permission)
            for permission in selectors.list_mail_rule_permissions(rule_id=rule_id)
        ],
    }


def _mail_rule_to_pattern_dict(rule) -> dict[str, object]:
    """메일 rule 모델에서 패턴 적용에 필요한 dict를 생성합니다."""

    return {
        "line_id": rule.line_id,
        "process_id": rule.process_id,
        "eds_step": rule.eds_step,
        "step_seq": rule.step_seq,
        "ppid": rule.ppid,
        "eqpch": rule.eqpch,
        "bin_name": rule.bin_name,
        "date_to": rule.date_to,
    }


def _filter_frame_for_mail_rule(merged: pd.DataFrame, rule) -> pd.DataFrame:
    """메일 알림 rule의 패턴과 심각도 조건에 맞는 row만 남깁니다."""

    if merged.empty:
        return merged
    allowed_statuses = MAIL_SEVERITY_STATUSES.get(rule.severity_mode, {"High Risk Chamber"})
    if "display_status" not in merged.columns:
        return merged.iloc[0:0]

    filtered = merged[merged["display_status"].isin(allowed_statuses)]
    if filtered.empty:
        return filtered

    rule_dict = _mail_rule_to_pattern_dict(rule)
    field_columns = [
        ("line_id", "line_id"),
        ("process_id", "process_id"),
        ("eds_step", "eds_step"),
        ("step_seq", "step_seq"),
        ("ppid", "ppid"),
        ("eqpch", "eqc"),
        ("bin_name", "bin_name"),
    ]
    mask = pd.Series(True, index=filtered.index)
    for field, column in field_columns:
        pattern = rule_dict.get(field) or "*"
        if pattern == "*":
            continue
        if column not in filtered.columns:
            return filtered.iloc[0:0]
        mask = mask & filtered[column].astype(str).apply(lambda v, p=pattern: _matches_pattern(v, p))

    return filtered[mask]


def _safe_string(value: Any) -> str:
    """메일 이벤트 키와 HTML 생성에 사용할 문자열로 정규화합니다."""

    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value)


def _build_mail_event_key(event: dict[str, object]) -> str:
    """이상감지 이벤트를 중복 판정용 안정 키로 변환합니다."""

    key_payload = {
        key: _safe_string(event.get(key))
        for key in (
            "date",
            "line_id",
            "process_id",
            "eds_step",
            "step_seq",
            "ppid",
            "eqc",
            "bin_name",
            "display_status",
        )
    }
    raw_key = json.dumps(key_payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _resolve_mail_rule_files(rule, *, today: str) -> list[Path]:
    """오늘 날짜 파일만 인덱스로 조회합니다. line/process/eds_step이 정확한 값이면 추가 필터링합니다."""

    def _is_exact(val: Any) -> bool:
        s = str(val) if val is not None else ""
        return bool(s) and s != "*" and "*" not in s and "?" not in s

    kwargs: dict[str, str] = {}
    if _is_exact(rule.line_id):
        kwargs["line_id"] = rule.line_id
    if _is_exact(rule.process_id):
        kwargs["process_id"] = rule.process_id
    if _is_exact(rule.eds_step):
        kwargs["eds_step"] = rule.eds_step

    files = selectors.query_indexed_files_by_range(date_from=today, date_to=today, **kwargs)
    if not files:
        # 인덱스 없거나 결과 없으면 날짜 디렉터리 직접 스캔
        files = selectors.iter_date_files(today)
    return files


def _collect_mail_rule_events(rule, *, today: str) -> list[dict[str, object]]:
    """메일 알림 rule에 매칭되는 오늘 날짜 이상감지 이벤트 목록을 수집합니다."""

    try:
        files = _resolve_mail_rule_files(rule, today=today)
    except FileNotFoundError as exc:
        raise L3SpiderServiceError(str(exc), status_code=404) from exc
    except NotADirectoryError as exc:
        raise L3SpiderServiceError(str(exc), status_code=400) from exc

    frames = _parallel_read(files, _read_mail_event_file)
    if not frames:
        return []

    merged = pd.concat(frames, ignore_index=True)
    merged = _normalize_display_status(merged)
    merged = _filter_frame_for_mail_rule(merged, rule)
    if merged.empty:
        return []

    group_columns = [
        "date",
        "line_id",
        "process_id",
        "eds_step",
        "step_seq",
        "ppid",
        "eqc",
        "bin_name",
        "display_status",
    ]
    available_group_columns = [column for column in group_columns if column in merged.columns]
    grouped = merged.groupby(available_group_columns, sort=True, dropna=False)
    events: list[dict[str, object]] = []
    for keys, group in grouped:
        key_values = keys if isinstance(keys, tuple) else (keys,)
        event = {
            column: _safe_string(value)
            for column, value in zip(available_group_columns, key_values)
        }
        event["line_name"] = line_name_rules.resolve_line_name(
            event.get("line_id", ""), event.get("process_id", ""), event.get("step_seq", "")
        )
        if "tkin_time" in group.columns:
            tkin = pd.to_datetime(group["tkin_time"], errors="coerce").dropna()
            event["latest_tkin_time"] = tkin.max().strftime("%Y-%m-%d %H:%M:%S") if not tkin.empty else ""
        event["row_count"] = int(len(group))
        event["event_key"] = _build_mail_event_key(event)
        events.append(event)
    return events


def _rule_local_today(rule, *, now: dt_datetime) -> "date":
    """rule 타임존 기준 오늘 날짜를 반환합니다."""
    try:
        tz = ZoneInfo(rule.timezone or "Asia/Seoul")
    except Exception:
        tz = ZoneInfo("Asia/Seoul")
    return now.astimezone(tz).date()


def _mail_rule_target_date(rule, *, now: dt_datetime) -> str:
    """메일에 담을 데이터 날짜(ISO 문자열)를 반환합니다.

    run_status에서 '오늘 이하에서 가장 최근 완료된 날짜'를 사용한다.
    즉 오늘 알고리즘이 아직 완료되지 않았으면 직전 완료 날짜(보통 어제)를 발송한다
    — 대시보드의 완결성 게이트와 동일 기준. 완료 날짜가 없으면 캘린더 오늘을 사용한다.
    """
    local_today = _rule_local_today(rule, now=now).isoformat()
    completed = selectors.query_completed_dates()
    if completed:
        candidates = [d for d in completed if d <= local_today]
        if candidates:
            return max(candidates)
    return local_today


def _is_mail_rule_due(rule, *, now: dt_datetime) -> bool:
    """현재 시각 기준으로 rule 발송 시간이 되었는지 판단합니다."""

    try:
        tz = ZoneInfo(rule.timezone or "Asia/Seoul")
    except Exception:
        tz = ZoneInfo("Asia/Seoul")
    local_now = now.astimezone(tz)
    local_today = local_now.date()
    # date_to 만료 체크
    if rule.date_to and local_today > rule.date_to:
        return False
    if local_now.time().replace(second=0, microsecond=0) < rule.send_time:
        return False
    checked_at = rule.last_checked_at or rule.last_sent_at
    if not checked_at:
        # 한 번도 발송하지 않은 rule. 오늘 발송 슬롯(send_time)이 rule 생성 전에 이미
        # 지났다면 오늘은 건너뛰고 다음 날 슬롯부터 발송한다.
        # (예: 09:00 설정을 13:00에 만들면 오늘 13:05 트리거에서 당일 발송하지 않음)
        created_local = rule.created_at.astimezone(tz)
        todays_slot = dt_datetime.combine(local_today, rule.send_time, tzinfo=tz)
        if created_local > todays_slot:
            return False
        return True
    return checked_at.astimezone(tz).date() < local_today


def _mark_mail_rule_checked(rule, *, sent: bool = False) -> None:
    """메일 rule의 일일 처리 시각을 갱신합니다."""

    checked_at = timezone.now()
    rule.last_checked_at = checked_at
    update_fields = ["last_checked_at", "updated_at"]
    if sent:
        rule.last_sent_at = checked_at
        update_fields.append("last_sent_at")
    rule.save(update_fields=update_fields)


def _resolve_l3_mail_sender() -> str:
    """L3 Spider 메일 발신자 주소를 settings/env에서 조회합니다."""

    return (
        getattr(settings, "L3_SPIDER_MAIL_SENDER", "")
        or getattr(settings, "DRONE_MAIL_SENDER", "")
        or ""
    ).strip()


def _build_l3_mail_subject(rule, events: list[dict[str, object]]) -> str:
    """L3 Spider 메일 제목을 생성합니다."""

    return f"[L3 Spider] 이상감지 {len(events)}건 - {rule.name}".strip()[:255]


def _resolve_l3_spider_mail_url() -> str:
    """메일 본문에 넣을 L3 Spider 화면 URL을 settings/env에서 생성합니다."""

    configured = str(getattr(settings, "L3_SPIDER_MAIL_TARGET_URL", "") or "").strip()
    if configured:
        return configured

    frontend_base = str(getattr(settings, "FRONTEND_BASE_URL", "") or "").strip()
    if not frontend_base:
        return ""
    return f"{frontend_base.rstrip('/')}/l3_spider"


def _build_l3_spider_event_url(base_url: str, event: dict[str, object]) -> str:
    """메일 이벤트 정보를 L3 Spider deep link query로 변환합니다."""

    if not base_url:
        return ""

    query_fields = [
        ("date", "date"),
        ("lineName", "line_name"),
        ("lineId", "line_id"),
        ("processId", "process_id"),
        ("edsStep", "eds_step"),
        ("stepSeq", "step_seq"),
        ("ppid", "ppid"),
        ("eqpch", "eqc"),
        ("binName", "bin_name"),
    ]
    event_query = [
        (query_name, value)
        for query_name, event_key in query_fields
        if (value := _safe_string(event.get(event_key)))
    ]
    if not event_query:
        return base_url

    parsed = urlparse(base_url)
    existing_query = parse_qsl(parsed.query, keep_blank_values=True)
    return urlunparse(parsed._replace(query=urlencode([*existing_query, *event_query])))


def _build_l3_mail_body(rule, events: list[dict[str, object]]) -> str:
    """L3 Spider 이상감지 digest HTML 본문을 생성합니다."""

    target_url = _resolve_l3_spider_mail_url()
    rows = []
    for event in events[:_MAIL_DIGEST_PREVIEW_LIMIT]:
        cells = [
            event.get("date"),
            event.get("line_name"),
            event.get("line_id"),
            event.get("process_id"),
            event.get("eds_step"),
            event.get("step_seq"),
            event.get("ppid"),
            event.get("eqc"),
            event.get("bin_name"),
            event.get("display_status"),
            event.get("latest_tkin_time"),
        ]
        td = 'style="padding:5px 14px;white-space:nowrap;"'
        event_url = _build_l3_spider_event_url(target_url, event)
        action_cell = (
            f'<td {td}><a href="{html.escape(event_url, quote=True)}" '
            'target="_blank" rel="noopener noreferrer">열기</a></td>'
            if event_url
            else f"<td {td}></td>"
        )
        rows.append(
            "<tr>"
            + "".join(f"<td {td}>{html.escape(_safe_string(value))}</td>" for value in cells)
            + action_cell
            + "</tr>"
        )

    remaining = max(0, len(events) - _MAIL_DIGEST_PREVIEW_LIMIT)
    remaining_text = f"<p>외 {remaining}건은 L3 Spider 화면에서 확인하세요.</p>" if remaining else ""
    action_html = ""
    if target_url:
        primary_url = _build_l3_spider_event_url(target_url, events[0]) if events else target_url
        escaped_url = html.escape(primary_url, quote=True)
        action_html = f"""
    <p>
      <a href="{escaped_url}" target="_blank" rel="noopener noreferrer"
         style="display:inline-block;padding:10px 14px;background:#2563eb;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:bold;">
        L3 Spider에서 확인
      </a>
    </p>
"""
    cell_style = "padding:5px 14px;white-space:nowrap;"
    th_style = cell_style + "background:#f3f4f6;font-weight:600;"
    return f"""
<html>
  <body style="font-family:sans-serif;font-size:13px;">
    <h3>L3 Spider 이상감지 알림</h3>
    <p>규칙: {html.escape(rule.name)}</p>
    <p>조건: {html.escape(rule.severity_mode)}</p>
    {action_html}
    <table border="1" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border-color:#d1d5db;">
      <thead>
        <tr>
          <th style="{th_style}">Date</th><th style="{th_style}">Line Name</th><th style="{th_style}">Line ID</th><th style="{th_style}">Process</th><th style="{th_style}">EDS Step</th><th style="{th_style}">Step</th>
          <th style="{th_style}">PPID</th><th style="{th_style}">EQPCH</th><th style="{th_style}">Bin</th><th style="{th_style}">Status</th><th style="{th_style}">Last TKin</th><th style="{th_style}">Link</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
    {remaining_text}
  </body>
</html>
"""


def _claim_mail_events(rule, events: list[dict[str, object]]) -> list[dict[str, object]]:
    """발송 전 delivery row를 생성해 이번 trigger가 처리할 이벤트만 선점합니다."""

    from ..models import L3SpiderMailDelivery

    claimed: list[dict[str, object]] = []
    for event in events:
        try:
            with transaction.atomic():
                L3SpiderMailDelivery.objects.create(
                    rule=rule,
                    event_key=event["event_key"],
                    status=L3SpiderMailDelivery.Statuses.PENDING,
                    event_date=_safe_string(event.get("date")),
                    display_status=_safe_string(event.get("display_status")),
                    receiver_emails=list(rule.receiver_emails or []),
                    payload_snapshot=event,
                )
            claimed.append(event)
        except IntegrityError:
            continue
    return claimed


def _mark_claimed_mail_events(
    *,
    rule,
    events: list[dict[str, object]],
    status: str,
    error_message: str = "",
) -> None:
    """선점한 delivery row의 최종 발송 상태를 갱신합니다."""

    from ..models import L3SpiderMailDelivery

    event_keys = [event["event_key"] for event in events]
    update_fields: dict[str, object] = {
        "status": status,
        "error_message": error_message[:2000],
    }
    if status == L3SpiderMailDelivery.Statuses.SENT:
        update_fields["sent_at"] = timezone.now()
    L3SpiderMailDelivery.objects.filter(
        rule=rule,
        event_key__in=event_keys,
        status=L3SpiderMailDelivery.Statuses.PENDING,
    ).update(**update_fields)


def _process_mail_rule(rule, *, now: dt_datetime) -> dict[str, object]:
    """단일 메일 rule의 due 여부 확인, 이벤트 수집, digest 발송을 처리합니다."""

    from ..models import L3SpiderMailDelivery

    if not _is_mail_rule_due(rule, now=now):
        return {"ruleId": rule.id, "status": "not_due", "claimed": 0, "sent": 0}

    # 발송 시점 기준 '최신 완료 날짜' 데이터를 담는다(오늘 미완이면 어제). 스케줄(하루 1회
    # 발송) 자체는 _is_mail_rule_due가 캘린더 오늘 기준으로 판단하므로 영향 없다.
    target_date = _mail_rule_target_date(rule, now=now)
    events = _collect_mail_rule_events(rule, today=target_date)
    if not events:
        _mark_mail_rule_checked(rule)
        return {"ruleId": rule.id, "status": "no_events", "claimed": 0, "sent": 0}

    claimed_events = _claim_mail_events(rule, events)
    if not claimed_events:
        _mark_mail_rule_checked(rule)
        return {"ruleId": rule.id, "status": "already_sent", "claimed": 0, "sent": 0}

    sender = _resolve_l3_mail_sender()
    if not sender:
        _mark_claimed_mail_events(
            rule=rule,
            events=claimed_events,
            status=L3SpiderMailDelivery.Statuses.FAILED,
            error_message="L3_SPIDER_MAIL_SENDER 미설정",
        )
        return {"ruleId": rule.id, "status": "failed", "claimed": len(claimed_events), "sent": 0}

    try:
        send_knox_mail_api(
            sender_email=sender,
            receiver_emails=rule.receiver_emails,
            subject=_build_l3_mail_subject(rule, claimed_events),
            html_content=_build_l3_mail_body(rule, claimed_events),
        )
    except Exception as exc:
        _mark_claimed_mail_events(
            rule=rule,
            events=claimed_events,
            status=L3SpiderMailDelivery.Statuses.FAILED,
            error_message=str(exc),
        )
        return {"ruleId": rule.id, "status": "failed", "claimed": len(claimed_events), "sent": 0}

    _mark_claimed_mail_events(
        rule=rule,
        events=claimed_events,
        status=L3SpiderMailDelivery.Statuses.SENT,
    )
    _mark_mail_rule_checked(rule, sent=True)
    return {
        "ruleId": rule.id,
        "status": "sent",
        "claimed": len(claimed_events),
        "sent": len(claimed_events),
    }


def send_mail_rule_test(rule_id: int, *, user: Any) -> dict[str, object]:
    """메일 rule을 정기 발송 이력과 분리해 단발성으로 테스트 발송합니다."""

    from ..models import L3SpiderMailRule

    user_id = _require_user_id(user)
    try:
        rule = selectors.get_mail_rule_for_user(rule_id=rule_id, user_id=user_id)
    except L3SpiderMailRule.DoesNotExist as exc:
        raise L3SpiderServiceError("Not found", status_code=404) from exc
    if not _mail_rule_access(rule, user_id=user_id)["canWrite"]:
        raise L3SpiderServiceError("Write permission required", status_code=403)
    if not rule.receiver_emails:
        raise L3SpiderServiceError("수신자가 없습니다.", status_code=400)

    today = _rule_local_today(rule, now=timezone.now()).isoformat()
    events = _collect_mail_rule_events(rule, today=today)
    if not events:
        return {
            "ruleId": rule.id,
            "status": "no_events",
            "sent": 0,
            "eventCount": 0,
            "receiverCount": len(rule.receiver_emails),
        }

    sender = _resolve_l3_mail_sender()
    if not sender:
        raise L3SpiderServiceError("L3_SPIDER_MAIL_SENDER 미설정", status_code=400)

    try:
        send_knox_mail_api(
            sender_email=sender,
            receiver_emails=rule.receiver_emails,
            subject=f"[TEST] {_build_l3_mail_subject(rule, events)}"[:255],
            html_content=_build_l3_mail_body(rule, events),
        )
    except Exception as exc:
        raise L3SpiderServiceError(f"테스트 메일 발송 실패: {exc}", status_code=502) from exc

    return {
        "ruleId": rule.id,
        "status": "sent",
        "sent": len(events),
        "eventCount": len(events),
        "receiverCount": len(rule.receiver_emails),
    }


def trigger_due_mail_rules(*, limit: int = 20, now: dt_datetime | None = None) -> dict[str, object]:
    """발송 시간이 된 활성 L3 Spider 메일 rule을 처리합니다.

    입력:
        limit: 한 번에 처리할 최대 rule 수.
        now: 테스트용 기준 시각. 없으면 현재 시각을 사용합니다.
    반환:
        처리 rule 수와 발송 결과 요약.
    부작용:
        L3SpiderMailDelivery 생성/갱신 및 외부 Mail API 호출이 발생합니다.
    """

    current = now or timezone.now()
    rules = list(selectors.list_active_mail_rules_for_trigger(limit=limit))
    results = [_process_mail_rule(rule, now=current) for rule in rules]
    return {
        "processed": len(results),
        "sent": sum(int(result.get("sent", 0)) for result in results),
        "claimed": sum(int(result.get("claimed", 0)) for result in results),
        "results": results,
    }
