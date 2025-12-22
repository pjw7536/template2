"""CRUD service helpers for DroneEarlyInform with defensive validations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction

from ..models import DroneEarlyInform


class DroneEarlyInformDuplicateError(RuntimeError):
    """DroneEarlyInform의 유니크 제약 위반(중복) 시 발생합니다."""


class DroneEarlyInformNotFoundError(RuntimeError):
    """DroneEarlyInform 레코드가 없을 때 발생합니다."""


@dataclass(frozen=True)
class DroneEarlyInformUpdateResult:
    """조기 알림 설정 업데이트 결과를 담습니다."""

    entry: DroneEarlyInform
    previous_entry: DroneEarlyInform


def create_early_inform_entry(
    *,
    line_id: str,
    main_step: str,
    custom_end_step: str | None,
    updated_by: str | None,
) -> DroneEarlyInform:
    """조기 알림 설정을 생성합니다.

    Side effects:
        Inserts a DroneEarlyInform row.
    """

    try:
        with transaction.atomic():
            return DroneEarlyInform.objects.create(
                line_id=line_id,
                main_step=main_step,
                custom_end_step=custom_end_step,
                updated_by=updated_by,
            )
    except IntegrityError as exc:
        raise DroneEarlyInformDuplicateError("An entry for this main step already exists") from exc


def update_early_inform_entry(
    *,
    entry_id: int,
    updates: dict[str, Any],
    updated_by: str | None,
) -> DroneEarlyInformUpdateResult:
    """조기 알림 설정을 부분 업데이트합니다.

    Side effects:
        Updates a DroneEarlyInform row.
    """

    allowed_fields = {"line_id", "main_step", "custom_end_step"}
    filtered_updates = {key: value for key, value in updates.items() if key in allowed_fields}

    if not filtered_updates and updated_by is None:
        raise ValueError("No valid fields to update")

    try:
        with transaction.atomic():
            entry = DroneEarlyInform.objects.select_for_update().filter(id=entry_id).first()
            if entry is None:
                raise DroneEarlyInformNotFoundError("Entry not found")

            previous_entry = DroneEarlyInform(
                id=entry.id,
                line_id=entry.line_id,
                main_step=entry.main_step,
                custom_end_step=entry.custom_end_step,
                updated_by=entry.updated_by,
                updated_at=entry.updated_at,
            )

            for key, value in filtered_updates.items():
                setattr(entry, key, value)
            entry.updated_by = updated_by
            entry.save()
    except IntegrityError as exc:
        raise DroneEarlyInformDuplicateError("An entry for this main step already exists") from exc

    return DroneEarlyInformUpdateResult(entry=entry, previous_entry=previous_entry)


def delete_early_inform_entry(*, entry_id: int) -> DroneEarlyInform:
    """조기 알림 설정을 삭제합니다.

    Side effects:
        Deletes a DroneEarlyInform row.
    """

    with transaction.atomic():
        entry = DroneEarlyInform.objects.select_for_update().filter(id=entry_id).first()
        if entry is None:
            raise DroneEarlyInformNotFoundError("Entry not found")
        entry.delete()
        return entry
