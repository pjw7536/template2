# =============================================================================
# 모듈 설명: 외부 예측 소속 스냅샷 동기화 서비스를 제공합니다.
# - 주요 대상: sync_external_affiliations
# - 불변 조건: knox_id는 외부 예측 소속의 고유 키로 사용합니다.
# =============================================================================

"""외부 예측 소속 스냅샷 동기화 서비스 모음.

- 주요 대상: sync_external_affiliations
- 주요 엔드포인트/클래스: 없음(서비스 함수 제공)
- 가정/불변 조건: knox_id는 외부 예측 소속의 고유 키로 사용됨
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from django.db import transaction
from django.utils import timezone

from ..models import ExternalAffiliationSnapshot
from .. import selectors
from .utils import _same_user_sdwt_prod


def _normalize_optional_text(value: Any) -> str | None:
    """선택 문자열 값을 공백 제거 후 없으면 None으로 반환합니다."""

    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _resolve_snapshot_username(
    *,
    record: dict[str, object],
) -> tuple[bool, str | None]:
    """동기화 레코드에 포함된 username 제공 여부와 정규화 값을 반환합니다."""

    if "username" not in record:
        return False, None
    return True, _normalize_optional_text(record.get("username"))


def sync_external_affiliations(
    *,
    records: Iterable[dict[str, object]],
) -> dict[str, int]:
    """외부 예측 소속 스냅샷만 업서트하며 등록된 소속은 보존합니다.

    입력:
    - records: knox_id/department/user_sdwt_prod/source_updated_at을 포함한 레코드 목록

    반환:
    - dict[str, int]: created/updated/unchanged/flagged 카운트

    부작용:
    - ExternalAffiliationSnapshot 업서트

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 카운터 및 입력 정규화
    # -----------------------------------------------------------------------------
    now = timezone.now()
    created = 0
    updated = 0
    unchanged = 0

    record_list = [record for record in records if isinstance(record, dict)]
    to_create: list[ExternalAffiliationSnapshot] = []
    to_update: list[ExternalAffiliationSnapshot] = []
    processed_existing_ids: list[str] = []
    bulk_batch_size = 5000
    # 동일 knox_id 중복 입력으로 인한 고유 제약 충돌을 피하려고 마지막 레코드로 정규화합니다.
    normalized_records: dict[str, dict[str, object]] = {}
    for record in record_list:
        knox_id = record.get("knox_id")
        if isinstance(knox_id, str) and knox_id.strip():
            normalized_records[knox_id.strip()] = record

    # -----------------------------------------------------------------------------
    # 2) 기존 스냅샷 조회
    # -----------------------------------------------------------------------------
    knox_ids = list(normalized_records.keys())
    existing = selectors.get_external_affiliation_snapshots_by_knox_ids(knox_ids=knox_ids)

    # -----------------------------------------------------------------------------
    # 3) 레코드별 변경/생성 목록 준비
    # -----------------------------------------------------------------------------
    for record in normalized_records.values():
        knox_id = (record.get("knox_id") or "").strip()
        department = (record.get("department") or "").strip()
        predicted = (record.get("user_sdwt_prod") or "").strip()
        source_updated_at = record.get("source_updated_at") or now
        if not knox_id or not predicted or not department:
            continue
        if isinstance(source_updated_at, datetime) and timezone.is_naive(source_updated_at):
            source_updated_at = timezone.make_aware(source_updated_at, timezone.utc)
        if not isinstance(source_updated_at, datetime):
            source_updated_at = now

        username_provided, username = _resolve_snapshot_username(
            record=record,
        )

        snapshot = existing.get(knox_id)
        if snapshot is None:
            snapshot = ExternalAffiliationSnapshot(
                knox_id=knox_id,
                username=username if username_provided else None,
                department=department,
                predicted_user_sdwt_prod=predicted,
                source_updated_at=source_updated_at,
                last_seen_at=now,
            )
            to_create.append(snapshot)
            created += 1
            continue

        processed_existing_ids.append(knox_id)

        # -----------------------------------------------------------------------------
        # 4) 변경 여부 판단
        # -----------------------------------------------------------------------------
        changed = not _same_user_sdwt_prod(snapshot.predicted_user_sdwt_prod, predicted)
        changed_department = (snapshot.department or "").strip() != department
        changed_source = snapshot.source_updated_at != source_updated_at
        changed_username = username_provided and (snapshot.username or "").strip() != (username or "")
        if changed or changed_department or changed_source or changed_username:
            if username_provided:
                snapshot.username = username
            snapshot.department = department
            snapshot.predicted_user_sdwt_prod = predicted
            snapshot.source_updated_at = source_updated_at
            to_update.append(snapshot)
            updated += 1
        else:
            unchanged += 1

    # -----------------------------------------------------------------------------
    # 5) 스냅샷 생성/갱신(벌크)
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        if to_create:
            ExternalAffiliationSnapshot.objects.bulk_create(to_create, batch_size=bulk_batch_size)
        if to_update:
            ExternalAffiliationSnapshot.objects.bulk_update(
                to_update,
                ["username", "department", "predicted_user_sdwt_prod", "source_updated_at"],
                batch_size=bulk_batch_size,
            )
        if processed_existing_ids:
            ExternalAffiliationSnapshot.objects.filter(knox_id__in=processed_existing_ids).update(last_seen_at=now)

    # 참조 갱신은 이미 등록한 사용자의 소속과 확인 상태에 영향을 주지 않습니다.
    return {"created": created, "updated": updated, "unchanged": unchanged, "flagged": 0}
