"""관리 명령에서 소속별 Grist document mapping을 안전하게 등록합니다."""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import GristDocumentScope
from ..selectors import (
    get_document_scope_by_keycloak_group_id,
    get_legacy_document_scope_by_affiliation_name,
)
from .access import enqueue_access_sync_for_group_ids


def _validate_launch_url(launch_url: str) -> str:
    """허용된 Grist host의 HTTP(S) URL만 launcher에 저장합니다."""

    normalized = str(launch_url or "").strip()
    parsed = urlparse(normalized)
    allowed_hosts = {
        str(host).strip().lower()
        for host in getattr(settings, "GRIST_ALLOWED_LAUNCH_HOSTS", [])
        if str(host).strip()
    }
    public_host = urlparse(str(getattr(settings, "GRIST_PUBLIC_URL", "") or "")).hostname
    if public_host:
        allowed_hosts.add(public_host.lower())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValidationError("launch_url은 유효한 HTTP(S) URL이어야 합니다.")
    if not allowed_hosts or parsed.hostname.lower() not in allowed_hosts:
        raise ValidationError("launch_url host가 GRIST_ALLOWED_LAUNCH_HOSTS에 없습니다.")
    return normalized


@transaction.atomic
def configure_document_scope(
    *,
    keycloak_group_id: str,
    affiliation_name: str,
    department: str = "",
    line: str = "",
    workspace_id: int,
    doc_id: str,
    equipment_table_id: str,
    worklog_table_id: str,
    task_table_id: str,
    launch_url: str,
    template_revision: str = "grist-work-hub-v1",
) -> tuple[GristDocumentScope, bool]:
    """소속의 Grist mapping을 저장하고 현재 document의 ACL 동기화를 적재합니다.

    한번 등록한 ``doc_id``는 Portal이 이전 document ACL을 추적하지 못하는 상황을
    방지하기 위해 변경할 수 없습니다. table과 launch metadata는 같은 document
    범위에서 갱신할 수 있습니다.
    """

    normalized_group_id = str(keycloak_group_id or "").strip()
    normalized_affiliation_name = str(affiliation_name or "").strip()
    if not normalized_group_id or not normalized_affiliation_name:
        raise ValidationError("Keycloak group ID와 표시용 소속 이름이 필요합니다.")
    normalized_doc_id = str(doc_id or "").strip()
    if not normalized_doc_id:
        raise ValidationError("doc_id가 필요합니다.")
    normalized_url = _validate_launch_url(launch_url)
    existing = get_document_scope_by_keycloak_group_id(group_id=normalized_group_id)
    if existing is None:
        existing = get_legacy_document_scope_by_affiliation_name(
            affiliation_name=normalized_affiliation_name
        )
    values = {
        "affiliation_snapshot": {
            "name": normalized_affiliation_name,
            "user_sdwt_prod": normalized_affiliation_name,
            "department": str(department or "").strip(),
            "line": str(line or "").strip(),
        },
        "workspace_id": workspace_id,
        "doc_id": normalized_doc_id,
        "equipment_table_id": str(equipment_table_id or "Equipment").strip(),
        "worklog_table_id": str(worklog_table_id or "WorkLog").strip(),
        "task_table_id": str(task_table_id or "Task").strip(),
        "launch_url": normalized_url,
        "template_revision": str(template_revision or "grist-work-hub-v1").strip(),
        "is_active": True,
    }
    if existing is None:
        document_scope = GristDocumentScope.objects.create(
            keycloak_group_id=normalized_group_id,
            **values,
        )
        created = True
    else:
        if existing.doc_id != normalized_doc_id:
            raise ValidationError(
                "기존 Grist mapping의 doc_id는 변경할 수 없습니다. "
                "새 소속 mapping으로 등록해주세요."
            )
        existing.keycloak_group_id = normalized_group_id
        for field_name, value in values.items():
            setattr(existing, field_name, value)
        existing.save(
            update_fields=["keycloak_group_id", *values.keys(), "updated_at"]
        )
        document_scope = existing
        created = False

    enqueue_access_sync_for_group_ids(
        group_ids=[normalized_group_id],
        reason="document_scope_configured",
    )
    return document_scope, created
