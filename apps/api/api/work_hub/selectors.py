"""Work Hub 로컬 mapping과 처리 이력을 읽는 selector입니다."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from django.db.models import Q, QuerySet

from .models import (
    GristAccessSyncOutbox,
    GristDocumentScope,
    GristWebhookReceipt,
)


def list_active_document_scopes_for_user_sdwt_prods(
    *,
    user_sdwt_prods: Iterable[str],
) -> QuerySet[GristDocumentScope]:
    """여러 user_sdwt_prod와 대소문자 구분 없이 일치하는 활성 mapping을 반환합니다."""

    query = Q()
    has_value = False
    for value in user_sdwt_prods:
        normalized = str(value or "").strip()
        if not normalized:
            continue
        query |= Q(affiliation__user_sdwt_prod__iexact=normalized)
        has_value = True
    if not has_value:
        return GristDocumentScope.objects.none()
    return (
        GristDocumentScope.objects.filter(
            query,
            is_active=True,
            affiliation__is_active=True,
        )
        .select_related("affiliation")
        .order_by("affiliation__user_sdwt_prod", "id")
    )


def list_active_document_scopes() -> QuerySet[GristDocumentScope]:
    """설비·권한 전체 동기화 대상인 활성 Grist mapping을 반환합니다."""

    return (
        GristDocumentScope.objects.filter(is_active=True, affiliation__is_active=True)
        .select_related("affiliation")
        .order_by("affiliation__user_sdwt_prod", "id")
    )


def list_access_reconciliation_document_scopes() -> QuerySet[GristDocumentScope]:
    """소속 비활성 여부와 무관하게 ACL reconciliation 대상 mapping을 반환합니다."""

    return (
        GristDocumentScope.objects.filter(is_active=True)
        .select_related("affiliation")
        .order_by("affiliation__user_sdwt_prod", "id")
    )


def get_access_reconciliation_document_scope_by_user_sdwt_prod(
    *, user_sdwt_prod: str
) -> GristDocumentScope | None:
    """소속 비활성 여부와 무관하게 식별자에 대응하는 활성 mapping을 반환합니다."""

    normalized = str(user_sdwt_prod or "").strip()
    if not normalized:
        return None
    return (
        GristDocumentScope.objects.filter(
            is_active=True,
            affiliation__user_sdwt_prod__iexact=normalized,
        )
        .select_related("affiliation")
        .order_by("id")
        .first()
    )


def list_enabled_document_scope_affiliation_ids() -> set[int]:
    """소속 비활성 여부와 무관하게 활성 document mapping의 소속 ID를 반환합니다."""

    return set(
        GristDocumentScope.objects.filter(is_active=True).values_list(
            "affiliation_id",
            flat=True,
        )
    )


def list_document_scopes_for_affiliation_ids(
    *, affiliation_ids: Iterable[int]
) -> QuerySet[GristDocumentScope]:
    """소속 비활성화 후 권한 회수도 가능하도록 활성 mapping을 반환합니다."""

    normalized_ids = {
        value for value in affiliation_ids if isinstance(value, int) and value > 0
    }
    if not normalized_ids:
        return GristDocumentScope.objects.none()
    return (
        GristDocumentScope.objects.filter(
            affiliation_id__in=normalized_ids,
            is_active=True,
        )
        .select_related("affiliation")
        .order_by("affiliation_id", "id")
    )


def get_reusable_access_sync_outbox(
    *, document_scope: GristDocumentScope
) -> GristAccessSyncOutbox | None:
    """같은 document의 아직 완료되지 않은 재사용 가능 Outbox를 반환합니다."""

    return (
        GristAccessSyncOutbox.objects.filter(
            document_scope=document_scope,
            status__in=(
                GristAccessSyncOutbox.Status.PENDING,
                GristAccessSyncOutbox.Status.FAILED,
                GristAccessSyncOutbox.Status.TERMINAL,
            ),
        )
        .order_by("id")
        .first()
    )


def list_ready_access_sync_outbox(
    *,
    limit: int,
    ready_before: datetime,
    stale_before: datetime,
    for_update: bool = False,
) -> list[GristAccessSyncOutbox]:
    """처리 가능하거나 오래 멈춘 Grist 접근 동기화 작업을 반환합니다."""

    if limit <= 0:
        return []
    queryset = GristAccessSyncOutbox.objects.filter(
        Q(
            status__in=(
                GristAccessSyncOutbox.Status.PENDING,
                GristAccessSyncOutbox.Status.FAILED,
            ),
            available_at__lte=ready_before,
        )
        | Q(
            status=GristAccessSyncOutbox.Status.PROCESSING,
            updated_at__lte=stale_before,
        )
    ).select_related("document_scope", "document_scope__affiliation")
    if for_update:
        queryset = queryset.select_for_update(skip_locked=True)
    return list(queryset.order_by("available_at", "id")[:limit])


def get_document_scope_by_doc_and_worklog_table(
    *,
    doc_id: str,
    table_id: str,
) -> GristDocumentScope | None:
    """Grist document와 WorkLog table ID로 활성 mapping을 반환합니다."""

    return (
        GristDocumentScope.objects.filter(
            doc_id=str(doc_id).strip(),
            worklog_table_id=str(table_id).strip(),
            is_active=True,
            affiliation__is_active=True,
        )
        .select_related("affiliation")
        .order_by("id")
        .first()
    )


def get_document_scope_by_affiliation_id(
    *,
    affiliation_id: int,
) -> GristDocumentScope | None:
    """소속 ID로 Grist document mapping을 반환합니다."""

    return (
        GristDocumentScope.objects.filter(affiliation_id=affiliation_id)
        .select_related("affiliation")
        .order_by("id")
        .first()
    )


def list_ready_webhook_receipts(
    *,
    limit: int,
    ready_before: datetime,
    stale_before: datetime,
    for_update: bool = False,
) -> list[GristWebhookReceipt]:
    """처리 가능하거나 임대가 만료된 Webhook receipt를 반환합니다."""

    if limit <= 0:
        return []
    queryset = GristWebhookReceipt.objects.filter(
        Q(
            status__in=(
                GristWebhookReceipt.Status.RECEIVED,
                GristWebhookReceipt.Status.FAILED,
            ),
            available_at__lte=ready_before,
        )
        | Q(
            status=GristWebhookReceipt.Status.PROCESSING,
            processed_at__lte=stale_before,
        )
        | Q(
            status=GristWebhookReceipt.Status.PROCESSING,
            processed_at__isnull=True,
        )
    )
    if for_update:
        queryset = queryset.select_for_update(skip_locked=True)
    return list(queryset.order_by("available_at", "id")[:limit])
