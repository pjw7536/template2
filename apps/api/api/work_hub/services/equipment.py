"""Observer 설비 기준정보를 Grist Equipment table에 투영합니다."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from api.observer import selectors as observer_selectors

from ..models import GristDocumentScope
from .client import GristClient


def sync_equipment_scope(
    *,
    document_scope: GristDocumentScope,
    dry_run: bool = False,
    client: GristClient | None = None,
) -> dict[str, int]:
    """한 소속의 설비를 equipment_id 기준으로 멱등 upsert하고 누락 record를 archive합니다."""

    grist = client or GristClient.from_settings()
    affiliation_name = str(
        document_scope.affiliation_snapshot.get("user_sdwt_prod")
        or document_scope.affiliation_snapshot.get("name")
        or ""
    )
    source_rows = observer_selectors.list_equipments_for_user_sdwt_prod(
        user_sdwt_prod=affiliation_name,
    )
    remote_rows = list(
        grist.iter_records(
            doc_id=document_scope.doc_id,
            table_id=document_scope.equipment_table_id,
        )
    )
    remote_by_id = {
        str(row.get("equipment_id") or "").strip(): row
        for row in remote_rows
        if str(row.get("equipment_id") or "").strip()
    }
    source_ids: set[str] = set()
    result = {"created": 0, "updated": 0, "archived": 0, "unchanged": 0}
    synced_at = timezone.now().isoformat()

    for source in source_rows:
        equipment_id = str(source.get("equipment_id") or "").strip()
        if not equipment_id:
            continue
        source_ids.add(equipment_id)
        values: dict[str, Any] = {
            "equipment_id": equipment_id,
            "line_id": source.get("line_id", ""),
            "sdwt_prod": source.get(
                "sdwt_prod",
                affiliation_name,
            ),
            "prc_group": source.get("prc_group", ""),
            "equipment_name": source.get("equipment_name", equipment_id),
            "is_active": True,
            "source_updated_at": synced_at,
            "archived": False,
        }
        remote = remote_by_id.get(equipment_id)
        if remote is None:
            result["created"] += 1
            if not dry_run:
                grist.create_record(
                    doc_id=document_scope.doc_id,
                    table_id=document_scope.equipment_table_id,
                    values=values,
                )
            continue
        comparable_fields = (
            "line_id",
            "sdwt_prod",
            "prc_group",
            "equipment_name",
            "is_active",
            "archived",
        )
        changed = any(remote.get(field) != values[field] for field in comparable_fields)
        if not changed:
            result["unchanged"] += 1
            continue
        result["updated"] += 1
        if not dry_run:
            grist.update_record(
                doc_id=document_scope.doc_id,
                table_id=document_scope.equipment_table_id,
                row_id=int(remote["id"]),
                values=values,
            )

    for equipment_id, remote in remote_by_id.items():
        if equipment_id in source_ids or remote.get("archived") is True:
            continue
        result["archived"] += 1
        if not dry_run:
            grist.update_record(
                doc_id=document_scope.doc_id,
                table_id=document_scope.equipment_table_id,
                row_id=int(remote["id"]),
                values={
                    "is_active": False,
                    "archived": True,
                    "source_updated_at": synced_at,
                },
            )
    return result
