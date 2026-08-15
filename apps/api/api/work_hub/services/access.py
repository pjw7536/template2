"""Portal 소속 권한을 Grist document ACL에 투영합니다."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from api.auth.services import KeycloakAdminClient, KeycloakError

from .. import selectors
from ..models import GristAccessSyncOutbox, GristDocumentScope
from .client import GristClient, GristConfigurationError, GristRequestError

logger = logging.getLogger(__name__)

PORTAL_TO_GRIST_ROLE = {
    "viewer": "viewers",
    "member": "editors",
    "manager": "owners",
}
GRIST_PUBLIC_EMAILS = {
    "anon@getgrist.com",
    "everyone@getgrist.com",
    "previewer@getgrist.com",
}
WORK_HUB_SCOPE_KEY = "work-hub"


def _desired_grist_users(
    document_scope: GristDocumentScope,
    *,
    keycloak_client: KeycloakAdminClient | None,
) -> dict[str, dict[str, str]]:
    """Keycloak group/client role을 email별 Grist document 역할로 변환합니다."""

    if not document_scope.is_active:
        return {}
    try:
        keycloak = keycloak_client or KeycloakAdminClient.from_settings()
        memberships = keycloak.get_affiliation_members(
            group_id=document_scope.keycloak_group_id
        )
        admins = keycloak.get_client_role_members(
            client_id=settings.OIDC_CLIENT_ID,
            role="work-hub-admin",
        )
    except KeycloakError:
        grace_seconds = int(
            getattr(settings, "KEYCLOAK_ACL_FAIL_CLOSED_SECONDS", 300) or 300
        )
        last_success = document_scope.keycloak_last_success_at
        if last_success and last_success >= timezone.now() - timedelta(seconds=grace_seconds):
            raise
        logger.error(
            "Keycloak 장기 조회 실패로 Grist ACL을 fail-closed 처리합니다: scope_id=%s",
            document_scope.id,
        )
        return {}

    document_scope.keycloak_last_success_at = timezone.now()
    document_scope.save(update_fields=["keycloak_last_success_at", "updated_at"])
    desired = {
        str(membership["email"]).casefold(): {
            "email": str(membership["email"]),
            "access": PORTAL_TO_GRIST_ROLE[str(membership["role"])],
        }
        for membership in memberships
        if membership.get("role") in PORTAL_TO_GRIST_ROLE
        and str(membership.get("email") or "").strip()
        and str(membership["email"]).strip().casefold() not in GRIST_PUBLIC_EMAILS
    }
    for admin in admins:
        email = str(admin.get("email") or "").strip()
        if email and email.casefold() not in GRIST_PUBLIC_EMAILS:
            desired[email.casefold()] = {"email": email, "access": "owners"}
    return desired


def sync_document_access_scope(
    *,
    document_scope: GristDocumentScope,
    dry_run: bool = False,
    client: GristClient | None = None,
    keycloak_client: KeycloakAdminClient | None = None,
) -> dict[str, int]:
    """Portal의 최종 사용자·역할 집합과 Grist document ACL을 동일하게 맞춥니다."""

    grist = client or GristClient.from_settings()
    desired = _desired_grist_users(
        document_scope,
        keycloak_client=keycloak_client,
    )
    access = grist.get_document_access(doc_id=document_scope.doc_id)
    current_users = access.get("users", []) if isinstance(access, dict) else []
    current = {
        str(item.get("email") or "").casefold(): item
        for item in current_users
        if isinstance(item, dict) and str(item.get("email") or "").strip()
    }
    changes: dict[str, str | None] = {}
    result = {"added": 0, "updated": 0, "removed": 0, "unchanged": 0}

    for key, target in desired.items():
        email = target["email"]
        target_access = target["access"]
        existing = current.get(key)
        if existing is None:
            changes[email] = target_access
            result["added"] += 1
        elif existing.get("access") != target_access or existing.get("parentAccess"):
            changes[email] = target_access
            result["updated"] += 1
        else:
            result["unchanged"] += 1

    for key, existing in current.items():
        email = str(existing.get("email") or "")
        if key in desired:
            continue
        changes[email] = None
        result["removed"] += 1

    inheritance_needs_update = access.get("maxInheritedRole", object()) is not None
    if (changes or inheritance_needs_update) and not dry_run:
        grist.update_document_access(
            doc_id=document_scope.doc_id,
            users=changes,
            max_inherited_role=None,
        )
    return result


@transaction.atomic
def enqueue_access_sync_for_affiliations(
    *,
    affiliation_ids: Iterable[int],
    reason: str = "portal_access_changed",
) -> int:
    """영향받는 소속 document에 desired-state 동기화 작업을 멱등 적재합니다.

    같은 document에 대기·실패 작업이 있으면 즉시 재시도할 수 있도록 재사용합니다.
    외부 Grist 호출은 전용 worker만 실행합니다.
    """

    normalized_reason = str(reason or "portal_access_changed").strip()[:64]
    scopes = selectors.list_document_scopes_for_affiliation_ids(
        affiliation_ids=affiliation_ids
    )
    queued = 0
    now = timezone.now()
    for scope in scopes:
        item = selectors.get_reusable_access_sync_outbox(document_scope=scope)
        if item is None:
            GristAccessSyncOutbox.objects.create(
                document_scope=scope,
                reason=normalized_reason,
                available_at=now,
            )
        else:
            item.reason = normalized_reason
            item.status = GristAccessSyncOutbox.Status.PENDING
            item.retry_count = 0
            item.available_at = now
            item.last_error = ""
            item.processed_at = None
            item.save(
                update_fields=[
                    "reason",
                    "status",
                    "retry_count",
                    "available_at",
                    "last_error",
                    "processed_at",
                    "updated_at",
                ]
            )
        queued += 1
    return queued


@transaction.atomic
def enqueue_access_sync_for_group_ids(
    *,
    group_ids: Iterable[str],
    reason: str = "keycloak_access_changed",
) -> int:
    """Keycloak parent group ID에 연결된 document ACL 작업을 멱등 적재합니다."""

    scopes = selectors.list_active_document_scopes_for_keycloak_group_ids(
        group_ids=group_ids
    )
    normalized_reason = str(reason or "keycloak_access_changed").strip()[:64]
    now = timezone.now()
    queued = 0
    for scope in scopes:
        item = selectors.get_reusable_access_sync_outbox(document_scope=scope)
        if item is None:
            GristAccessSyncOutbox.objects.create(
                document_scope=scope,
                reason=normalized_reason,
                available_at=now,
            )
        else:
            item.reason = normalized_reason
            item.status = GristAccessSyncOutbox.Status.PENDING
            item.retry_count = 0
            item.available_at = now
            item.last_error = ""
            item.processed_at = None
            item.save(
                update_fields=[
                    "reason",
                    "status",
                    "retry_count",
                    "available_at",
                    "last_error",
                    "processed_at",
                    "updated_at",
                ]
            )
        queued += 1
    return queued


def enqueue_access_sync_for_all_affiliations(
    *,
    reason: str = "portal_access_policy_changed",
) -> int:
    """활성 Work Hub document 전체에 desired-state 동기화를 적재합니다."""

    return enqueue_access_sync_for_group_ids(
        group_ids=selectors.list_enabled_document_scope_group_ids(),
        reason=reason,
    )


def reconcile_all_document_access_scopes(
    *,
    client: GristClient | None = None,
) -> dict[str, int]:
    """모든 활성 document ACL을 Portal 기준으로 맞추고 개별 실패를 격리합니다."""

    scopes = list(selectors.list_access_reconciliation_document_scopes())
    result = {"processed": len(scopes), "succeeded": 0, "failed": 0}
    if not scopes:
        return result
    try:
        grist = client or GristClient.from_settings()
    except Exception:
        logger.exception("Grist 전체 접근 권한 동기화 client 준비 실패")
        result["failed"] = len(scopes)
        return result
    try:
        keycloak: KeycloakAdminClient | None = KeycloakAdminClient.from_settings()
    except KeycloakError:
        keycloak = None
    for scope in scopes:
        try:
            sync_document_access_scope(
                document_scope=scope,
                client=grist,
                keycloak_client=keycloak,
            )
        except Exception:
            logger.exception(
                "Grist 전체 접근 권한 동기화 실패: document_scope_id=%s",
                scope.id,
            )
            result["failed"] += 1
        else:
            result["succeeded"] += 1
    return result


def _retry_delay_seconds(retry_count: int) -> int:
    """반복 장애가 Portal DB에 부하를 주지 않도록 재시도 간격을 제한합니다."""

    return min(900, 5 * (2 ** min(max(retry_count, 1), 8)))


def prune_completed_access_sync_outbox(*, retention_days: int) -> int:
    """보존 기간이 지난 완료 Outbox만 삭제하고 삭제 건수를 반환합니다."""

    if retention_days <= 0:
        return 0
    cutoff = timezone.now() - timedelta(days=retention_days)
    deleted, _details = GristAccessSyncOutbox.objects.filter(
        status=GristAccessSyncOutbox.Status.DONE,
        processed_at__isnull=False,
        processed_at__lt=cutoff,
    ).delete()
    return deleted


def _is_retryable_access_sync_error(exc: Exception) -> bool:
    """명시적으로 영구 분류된 설정·요청 오류는 재시도 대상에서 제외합니다."""

    if isinstance(exc, GristConfigurationError):
        return False
    if isinstance(exc, GristRequestError):
        return exc.retryable
    return True


def process_access_sync_outbox_batch(*, limit: int = 100) -> dict[str, int]:
    """대기 중인 접근 권한 Outbox를 잠그고 항목별 성공·재시도를 기록합니다."""

    if limit <= 0:
        return {"processed": 0, "succeeded": 0, "failed": 0}
    now = timezone.now()
    with transaction.atomic():
        pending = selectors.list_ready_access_sync_outbox(
            limit=limit,
            ready_before=now,
            stale_before=now - timedelta(minutes=10),
            for_update=True,
        )
        if not pending:
            return {"processed": 0, "succeeded": 0, "failed": 0}
        GristAccessSyncOutbox.objects.filter(
            id__in=[item.id for item in pending]
        ).update(
            status=GristAccessSyncOutbox.Status.PROCESSING,
            updated_at=now,
        )

    succeeded = 0
    failed = 0
    for item in pending:
        try:
            sync_document_access_scope(document_scope=item.document_scope)
            GristAccessSyncOutbox.objects.filter(id=item.id).update(
                status=GristAccessSyncOutbox.Status.DONE,
                last_error="",
                processed_at=timezone.now(),
                updated_at=timezone.now(),
            )
            succeeded += 1
        except Exception as exc:
            logger.exception("Grist 접근 권한 동기화 실패: outbox_id=%s", item.id)
            retry_count = item.retry_count + 1
            failed_at = timezone.now()
            retryable = _is_retryable_access_sync_error(exc)
            GristAccessSyncOutbox.objects.filter(id=item.id).update(
                status=(
                    GristAccessSyncOutbox.Status.FAILED
                    if retryable
                    else GristAccessSyncOutbox.Status.TERMINAL
                ),
                retry_count=retry_count,
                available_at=(
                    failed_at + timedelta(seconds=_retry_delay_seconds(retry_count))
                    if retryable
                    else failed_at
                ),
                last_error=str(exc),
                updated_at=failed_at,
            )
            failed += 1
    return {"processed": len(pending), "succeeded": succeeded, "failed": failed}
