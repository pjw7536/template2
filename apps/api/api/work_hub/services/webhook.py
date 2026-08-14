"""Grist WorkLog Webhook을 Task 생성으로 멱등하게 연결합니다."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .. import selectors
from ..models import GristTaskLink, GristWebhookReceipt
from .client import GristClient, GristConfigurationError, GristRequestError


logger = logging.getLogger(__name__)


class WebhookConflictError(RuntimeError):
    """같은 event ID가 서로 다른 payload에 재사용될 때 발생합니다."""


class WebhookMappingError(RuntimeError):
    """Webhook document/table에 대응하는 활성 Work Hub mapping이 없을 때 발생합니다."""


class WebhookProcessingDeferred(RuntimeError):
    """같은 WorkLog row가 처리 중이라 Webhook을 나중에 재시도할 때 사용합니다."""


_PROCESSING_LEASE = timedelta(minutes=2)
_MAX_ATTEMPTS = 8


def build_grist_webhook_token(*, doc_id: str, table_id: str) -> str:
    """마스터 secret에서 document·table 전용 Webhook token을 파생합니다."""

    secret = str(getattr(settings, "GRIST_WEBHOOK_SECRET", "") or "")
    normalized_doc_id = str(doc_id or "").strip()
    normalized_table_id = str(table_id or "").strip()
    if not secret or not normalized_doc_id or not normalized_table_id:
        return ""
    identifiers = json.dumps(
        [normalized_doc_id, normalized_table_id],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    scope = f"work-hub-webhook:v1:{identifiers}"
    return hmac.new(
        secret.encode("utf-8"),
        scope.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def prune_completed_webhook_receipts(*, retention_days: int) -> int:
    """보존 기간이 지난 완료 Webhook receipt만 삭제하고 삭제 건수를 반환합니다."""

    if retention_days <= 0:
        return 0
    cutoff = timezone.now() - timedelta(days=retention_days)
    deleted, _details = GristWebhookReceipt.objects.filter(
        status=GristWebhookReceipt.Status.DONE,
        processed_at__isnull=False,
        processed_at__lt=cutoff,
    ).delete()
    return deleted


def prune_failed_webhook_receipts(*, retention_days: int) -> int:
    """보존 기간이 지난 실패 Webhook receipt를 삭제하고 삭제 건수를 반환합니다."""

    if retention_days <= 0:
        return 0
    cutoff = timezone.now() - timedelta(days=retention_days)
    deleted, _details = GristWebhookReceipt.objects.filter(
        status__in=(
            GristWebhookReceipt.Status.FAILED,
            GristWebhookReceipt.Status.TERMINAL,
        ),
        processed_at__isnull=False,
        processed_at__lt=cutoff,
    ).delete()
    return deleted


def _hash_payload(payload: dict[str, Any]) -> str:
    """동일 payload 여부를 확인할 SHA-256을 생성합니다."""

    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _extract_row(item: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Grist의 평탄한 Webhook record에서 row ID와 field 값을 추출합니다."""

    row_id = item.get("id")
    if not row_id:
        raise ValueError("Webhook item에 WorkLog row ID가 없습니다.")
    values = {key: value for key, value in item.items() if key not in {"id", "manualSort"}}
    return int(row_id), values


def _is_truthy(value: Any) -> bool:
    """Webhook boolean 값을 엄격한 true 값으로 정규화합니다."""

    return value is True or (
        isinstance(value, str)
        and value.strip().lower() in {"true", "1", "yes"}
    )


def _has_reference(value: Any) -> bool:
    """Grist Ref field가 실제 row를 가리키는지 확인합니다."""

    try:
        return int(value or 0) > 0
    except (TypeError, ValueError):
        return False


def _build_task_values(*, scope: Any, row_id: int, values: dict[str, Any]) -> dict[str, Any]:
    """WorkLog field를 동일 document의 Task record 값으로 변환합니다."""

    equipment_row_id = int(values.get("equipment") or 0)
    equipment_label = f"설비 #{equipment_row_id}" if equipment_row_id else "설비"
    symptom = str(values.get("symptom") or "후속 조치").strip()
    task_values: dict[str, Any] = {
        "task_key": f"grist-worklog:{scope.doc_id}:{scope.worklog_table_id}:{row_id}",
        "title": f"[{equipment_label}] {symptom[:80]}",
        "description": str(values.get("action") or symptom).strip(),
        "source_worklog": row_id,
        "sdwt_prod": str(
            scope.affiliation_snapshot.get("user_sdwt_prod")
            or scope.affiliation_snapshot.get("name")
            or ""
        ),
        "status": "open",
        "priority": "normal",
        "archived": False,
    }
    if equipment_row_id:
        task_values["equipment"] = equipment_row_id
    return task_values


def _normalize_webhook_payload(
    *,
    doc_id: str,
    table_id: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Webhook payload를 멱등 hash와 저장에 사용할 형태로 정규화합니다."""

    return {
        "doc_id": str(doc_id).strip(),
        "table_id": str(table_id).strip(),
        "rows": rows,
    }


@transaction.atomic
def enqueue_grist_webhook(
    *,
    doc_id: str,
    table_id: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """검증된 Grist Webhook을 receipt queue에 멱등하게 적재합니다."""

    normalized_payload = _normalize_webhook_payload(
        doc_id=doc_id,
        table_id=table_id,
        rows=rows,
    )
    scope = selectors.get_document_scope_by_doc_and_worklog_table(
        doc_id=normalized_payload["doc_id"],
        table_id=normalized_payload["table_id"],
    )
    if scope is None:
        raise WebhookMappingError(
            "Webhook document/table에 대응하는 활성 mapping이 없습니다."
        )

    payload_hash = _hash_payload(normalized_payload)
    event_id = f"grist:{payload_hash}"
    first_row_id = None
    if rows:
        try:
            first_row_id, _values = _extract_row(rows[0])
        except (TypeError, ValueError):
            first_row_id = None
    now = timezone.now()

    receipt, created = GristWebhookReceipt.objects.select_for_update().get_or_create(
        event_id=event_id,
        defaults={
            "event_type": "rows.changed",
            "doc_id": normalized_payload["doc_id"],
            "table_id": normalized_payload["table_id"],
            "row_id": first_row_id,
            "payload_hash": payload_hash,
            "payload": normalized_payload,
            "available_at": now,
        },
    )
    if not created and receipt.payload_hash != payload_hash:
        raise WebhookConflictError("같은 event ID에 다른 payload가 전달되었습니다.")

    duplicate = not created
    processing_is_active = (
        receipt.status == GristWebhookReceipt.Status.PROCESSING
        and receipt.processed_at is not None
        and receipt.processed_at > now - _PROCESSING_LEASE
    )
    if not created and not processing_is_active:
        receipt.payload = normalized_payload
        receipt.row_id = first_row_id
        receipt.status = GristWebhookReceipt.Status.RECEIVED
        receipt.available_at = now
        receipt.last_error = ""
        receipt.processed_at = None
        receipt.save(
            update_fields=[
                "payload",
                "row_id",
                "status",
                "available_at",
                "last_error",
                "processed_at",
            ]
        )
    return {
        "event_id": event_id,
        "duplicate": duplicate,
        "status": receipt.status,
    }


def _claim_next_webhook_receipt() -> GristWebhookReceipt | None:
    """worker가 처리할 다음 receipt 하나의 임대를 획득합니다."""

    now = timezone.now()
    with transaction.atomic():
        ready = selectors.list_ready_webhook_receipts(
            limit=1,
            ready_before=now,
            stale_before=now - _PROCESSING_LEASE,
            for_update=True,
        )
        if not ready:
            return None
        receipt = ready[0]
        receipt.status = GristWebhookReceipt.Status.PROCESSING
        receipt.attempt_count += 1
        receipt.last_error = ""
        receipt.processed_at = now
        receipt.save(
            update_fields=["status", "attempt_count", "last_error", "processed_at"]
        )
        return receipt


def _touch_webhook_receipt(*, event_id: str, attempt_count: int) -> None:
    """긴 batch 처리 중 현재 Webhook receipt의 임대를 갱신합니다."""

    GristWebhookReceipt.objects.filter(
        event_id=event_id,
        status=GristWebhookReceipt.Status.PROCESSING,
        attempt_count=attempt_count,
    ).update(processed_at=timezone.now())


def _finish_webhook_receipt(
    *,
    event_id: str,
    attempt_count: int,
    status: str,
    last_error: str = "",
) -> None:
    """현재 처리 시도와 일치할 때만 receipt의 최종 상태를 저장합니다."""

    GristWebhookReceipt.objects.filter(
        event_id=event_id,
        status=GristWebhookReceipt.Status.PROCESSING,
        attempt_count=attempt_count,
    ).update(
        status=status,
        last_error=last_error,
        available_at=timezone.now(),
        processed_at=timezone.now(),
    )


def _retry_delay_seconds(attempt_count: int) -> int:
    """Webhook 반복 장애에 지수 backoff를 적용하고 최대 15분으로 제한합니다."""

    return min(900, 5 * (2 ** min(max(attempt_count, 1), 8)))


def _is_retryable_webhook_error(exc: Exception) -> bool:
    """설정·영구 Grist 오류를 제외한 Webhook 처리 실패만 재시도합니다."""

    if isinstance(exc, GristConfigurationError):
        return False
    if isinstance(exc, GristRequestError):
        return exc.retryable
    return True


def _fail_webhook_receipt(
    *,
    receipt: GristWebhookReceipt,
    exc: Exception,
) -> None:
    """실패한 receipt를 backoff 재시도 또는 terminal 상태로 전환합니다."""

    failed_at = timezone.now()
    retryable = (
        _is_retryable_webhook_error(exc)
        and receipt.attempt_count < _MAX_ATTEMPTS
    )
    GristWebhookReceipt.objects.filter(
        id=receipt.id,
        status=GristWebhookReceipt.Status.PROCESSING,
        attempt_count=receipt.attempt_count,
    ).update(
        status=(
            GristWebhookReceipt.Status.FAILED
            if retryable
            else GristWebhookReceipt.Status.TERMINAL
        ),
        available_at=(
            failed_at
            + timedelta(seconds=_retry_delay_seconds(receipt.attempt_count))
            if retryable
            else failed_at
        ),
        last_error=f"{type(exc).__name__}: {str(exc)[:300]}",
        processed_at=failed_at,
    )


@transaction.atomic
def _claim_task_link(
    *,
    scope: Any,
    row_id: int,
    task_key: str,
) -> tuple[int, int | None] | None:
    """Task link를 잠깐 잠가 원격 동기화를 수행할 처리 임대를 획득합니다."""

    task_link, created = GristTaskLink.objects.select_for_update().get_or_create(
        document_scope=scope,
        worklog_row_id=row_id,
        defaults={"task_key": task_key, "task_row_id": None},
    )
    now = timezone.now()
    lease_cutoff = now - _PROCESSING_LEASE
    if (
        not created
        and task_link.task_row_id is None
        and task_link.updated_at > lease_cutoff
    ):
        return None

    previous_task_row_id = task_link.task_row_id
    if not created:
        # NULL은 원격 처리 중임을 나타내며 transaction 종료 뒤 다른 요청이 대기합니다.
        task_link.task_row_id = None
        task_link.task_key = task_key
        task_link.save(update_fields=["task_row_id", "task_key", "updated_at"])
    return task_link.id, previous_task_row_id


@transaction.atomic
def _release_task_link(
    *,
    task_link_id: int,
    previous_task_row_id: int | None,
) -> None:
    """원격 처리 실패 시 Task link 임대를 이전 상태로 되돌립니다."""

    task_link = (
        GristTaskLink.objects.select_for_update()
        .filter(id=task_link_id, task_row_id__isnull=True)
        .first()
    )
    if task_link is None:
        return
    if previous_task_row_id is None:
        task_link.delete()
        return
    task_link.task_row_id = previous_task_row_id
    task_link.save(update_fields=["task_row_id", "updated_at"])


def _complete_task_link(*, task_link_id: int, task_row_id: int, task_key: str) -> None:
    """원격 처리가 끝난 Task row ID를 짧은 DB 갱신으로 확정합니다."""

    updated = GristTaskLink.objects.filter(
        id=task_link_id,
        task_row_id__isnull=True,
    ).update(
        task_row_id=task_row_id,
        task_key=task_key,
        updated_at=timezone.now(),
    )
    if not updated:
        raise RuntimeError("Task link 처리 임대를 확정하지 못했습니다.")


def _ensure_task_for_row(
    *,
    scope: Any,
    row_id: int,
    values: dict[str, Any],
    client: GristClient,
) -> bool:
    """후속 조치 조건을 만족하는 WorkLog에 Task를 한 번만 생성·연결합니다."""

    if not _is_truthy(values.get("follow_up_required")):
        return False
    if _is_truthy(values.get("archived")) or _has_reference(values.get("task")):
        return False

    task_key = f"grist-worklog:{scope.doc_id}:{scope.worklog_table_id}:{row_id}"
    claim = _claim_task_link(
        scope=scope,
        row_id=row_id,
        task_key=task_key,
    )
    if claim is None:
        raise WebhookProcessingDeferred(
            "같은 WorkLog row의 이전 Webhook 처리가 아직 진행 중입니다."
        )
    task_link_id, previous_task_row_id = claim
    try:
        # WorkLog 참조가 비어 있으면 원격 task_key로 삭제·재생성 여부를 확인합니다.
        remote_task = client.find_record_by_field(
            doc_id=scope.doc_id,
            table_id=scope.task_table_id,
            field_name="task_key",
            value=task_key,
        )
        task_created = False
        if remote_task:
            task_row_id = int(remote_task["id"])
        else:
            created_task = client.create_record(
                doc_id=scope.doc_id,
                table_id=scope.task_table_id,
                values=_build_task_values(scope=scope, row_id=row_id, values=values),
            )
            task_row_id = int(created_task["id"])
            task_created = True

        client.update_record(
            doc_id=scope.doc_id,
            table_id=scope.worklog_table_id,
            row_id=row_id,
            values={"task": task_row_id},
        )
        _complete_task_link(
            task_link_id=task_link_id,
            task_row_id=task_row_id,
            task_key=task_key,
        )
    except Exception:
        _release_task_link(
            task_link_id=task_link_id,
            previous_task_row_id=previous_task_row_id,
        )
        raise
    return task_created


def _process_claimed_webhook_receipt(
    *,
    receipt: GristWebhookReceipt,
    client: GristClient | None = None,
) -> int:
    """임대를 획득한 receipt의 WorkLog를 Grist Task로 동기화합니다."""

    payload = receipt.payload
    if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
        raise ValueError("저장된 Webhook payload 형식이 올바르지 않습니다.")
    doc_id = str(payload.get("doc_id") or "").strip()
    table_id = str(payload.get("table_id") or "").strip()
    rows = payload["rows"]
    scope = selectors.get_document_scope_by_doc_and_worklog_table(
        doc_id=doc_id,
        table_id=table_id,
    )
    if scope is None:
        raise WebhookMappingError(
            "Webhook document/table에 대응하는 활성 mapping이 없습니다."
        )
    grist = client or GristClient.from_settings()
    tasks_created = 0
    for item in rows:
        row_id, values = _extract_row(item)
        if _ensure_task_for_row(
            scope=scope,
            row_id=row_id,
            values=values,
            client=grist,
        ):
            tasks_created += 1
        _touch_webhook_receipt(
            event_id=receipt.event_id,
            attempt_count=receipt.attempt_count,
        )
    return tasks_created


def _run_claimed_webhook_receipt(
    *,
    receipt: GristWebhookReceipt,
    client: GristClient | None = None,
) -> int:
    """Webhook 외부 처리를 실행하고 receipt 최종 상태를 기록합니다."""

    try:
        tasks_created = _process_claimed_webhook_receipt(
            receipt=receipt,
            client=client,
        )
    except Exception as exc:
        _fail_webhook_receipt(receipt=receipt, exc=exc)
        raise
    _finish_webhook_receipt(
        event_id=receipt.event_id,
        attempt_count=receipt.attempt_count,
        status=GristWebhookReceipt.Status.DONE,
    )
    return tasks_created


def process_grist_webhook_batch(
    *,
    limit: int = 20,
    client: GristClient | None = None,
) -> dict[str, int]:
    """worker가 준비된 Webhook receipt를 하나씩 임대해 처리합니다."""

    if limit <= 0:
        return {"processed": 0, "succeeded": 0, "failed": 0}
    processed = 0
    succeeded = 0
    failed = 0
    for _index in range(limit):
        receipt = _claim_next_webhook_receipt()
        if receipt is None:
            break
        processed += 1
        try:
            _run_claimed_webhook_receipt(receipt=receipt, client=client)
        except WebhookProcessingDeferred:
            failed += 1
        except Exception:
            logger.exception(
                "Grist Webhook 처리 실패: receipt_id=%s",
                receipt.id,
            )
            failed += 1
        else:
            succeeded += 1
    return {"processed": processed, "succeeded": succeeded, "failed": failed}
