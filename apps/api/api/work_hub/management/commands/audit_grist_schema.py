"""등록된 Work Hub Grist table column 계약을 점검합니다."""

from django.core.management.base import BaseCommand, CommandError

from api.work_hub.selectors import list_active_document_scopes
from api.work_hub.services.client import GristClient


REQUIRED_COLUMNS = {
    "equipment": {
        "equipment_id": "Text",
        "line_id": "Text",
        "sdwt_prod": "Text",
        "prc_group": "Text",
        "equipment_name": "Text",
        "is_active": "Bool",
        "source_updated_at": "DateTime:UTC",
        "archived": "Bool",
    },
    "worklog": {
        "worklog_key": "Text",
        "work_date": "Date",
        "shift_code": "Text",
        "occurred_at": "DateTime:UTC",
        "equipment": "Ref:Equipment",
        "sdwt_prod": "Text",
        "writer": "Text",
        "symptom": "Text",
        "cause": "Text",
        "action": "Text",
        "result": "Text",
        "status": "Text",
        "handover_required": "Bool",
        "follow_up_required": "Bool",
        "task": "Ref:Task",
        "archived": "Bool",
    },
    "task": {
        "task_key": "Text",
        "title": "Text",
        "description": "Text",
        "source_worklog": "Ref:WorkLog",
        "equipment": "Ref:Equipment",
        "sdwt_prod": "Text",
        "assignee": "Text",
        "status": "Text",
        "priority": "Text",
        "due_at": "DateTime:UTC",
        "resolution": "Text",
        "reviewer": "Text",
        "completed_at": "DateTime:UTC",
        "archived": "Bool",
    },
}


class Command(BaseCommand):
    """Grist schema가 v1 column 계약을 만족하는지 보고합니다."""

    help = "활성 Grist mapping의 Equipment/WorkLog/Task column을 검사합니다."

    def handle(self, *args, **options) -> None:
        """누락 또는 type 불일치 column이 있으면 rollout을 차단합니다."""

        client = GristClient.from_settings()
        failures: list[str] = []
        for scope in list_active_document_scopes():
            tables = {
                "equipment": scope.equipment_table_id,
                "worklog": scope.worklog_table_id,
                "task": scope.task_table_id,
            }
            for table_name, table_id in tables.items():
                actual: dict[str, str] = {}
                for column in client.list_columns(
                    doc_id=scope.doc_id,
                    table_id=table_id,
                ):
                    column_id = str(column.get("id") or "").strip()
                    if not column_id:
                        continue
                    fields = column.get("fields")
                    column_fields = fields if isinstance(fields, dict) else {}
                    actual[column_id] = str(column_fields.get("type") or "Any")

                expected = REQUIRED_COLUMNS[table_name]
                missing = sorted(set(expected) - set(actual))
                mismatched = sorted(
                    f"{column_id}(type={actual[column_id]}, expected={expected_type})"
                    for column_id, expected_type in expected.items()
                    if column_id in actual and actual[column_id] != expected_type
                )
                violations: list[str] = []
                if missing:
                    violations.append(f"missing={', '.join(missing)}")
                if mismatched:
                    violations.append(f"mismatched={', '.join(mismatched)}")
                if violations:
                    failures.append(
                        f"{scope.keycloak_group_id}/{table_name}: "
                        + "; ".join(violations)
                    )
        if failures:
            raise CommandError("Grist schema 계약 위반\n" + "\n".join(failures))
        self.stdout.write(self.style.SUCCESS("모든 활성 Work Hub Grist schema가 v1 계약을 만족합니다."))
