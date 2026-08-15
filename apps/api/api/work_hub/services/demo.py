"""로컬 개발용 Grist 업무일지 구조와 더미 record를 멱등하게 구성합니다.

주요 함수:
- ``seed_grist_demo``: demo document, table, column, record와 Portal mapping을 보장합니다.

Portal 관리자 API key로 공식 Grist REST API만 사용합니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping
from urllib.parse import urlencode

from django.conf import settings

from .access import sync_document_access_scope
from .client import GristClient, GristRequestError
from .configuration import configure_document_scope
from .webhook import build_grist_webhook_token


class GristDemoError(RuntimeError):
    """개발용 Grist 초기화가 안전하게 완료되지 못했을 때 발생합니다."""


@dataclass(frozen=True)
class GristDemoResult:
    """생성 또는 재사용된 demo 리소스 식별자를 반환합니다."""

    workspace_id: int
    doc_id: str
    equipment_table_id: str
    worklog_table_id: str
    task_table_id: str
    equipment_rows: int
    worklog_rows: int
    task_rows: int
    mapping_created: bool


def _column(column_id: str, label: str, column_type: str = "Text") -> dict[str, Any]:
    """Grist table 생성 API가 사용하는 column 정의를 만듭니다."""

    return {
        "id": column_id,
        "fields": {
            "label": label,
            "type": column_type,
        },
    }


EQUIPMENT_COLUMNS = [
    _column("equipment_id", "설비 ID"),
    _column("line_id", "라인 ID"),
    _column("sdwt_prod", "소속"),
    _column("prc_group", "공정 그룹"),
    _column("equipment_name", "설비명"),
    _column("is_active", "활성", "Bool"),
    _column("source_updated_at", "기준정보 동기화 시각", "DateTime:UTC"),
    _column("archived", "보관", "Bool"),
]

WORKLOG_COLUMNS = [
    _column("worklog_key", "업무일지 키"),
    _column("work_date", "근무일", "Date"),
    _column("shift_code", "Shift"),
    _column("occurred_at", "발생 시각", "DateTime:UTC"),
    _column("equipment", "설비", "Ref:Equipment"),
    _column("sdwt_prod", "소속"),
    _column("writer", "작성자"),
    _column("symptom", "현상"),
    _column("cause", "원인"),
    _column("action", "조치"),
    _column("result", "결과"),
    _column("status", "상태"),
    _column("handover_required", "인수인계 필요", "Bool"),
    _column("follow_up_required", "후속 조치 필요", "Bool"),
    _column("archived", "보관", "Bool"),
]

TASK_COLUMNS = [
    _column("task_key", "Task 키"),
    _column("title", "제목"),
    _column("description", "설명"),
    _column("source_worklog", "원본 업무일지", "Ref:WorkLog"),
    _column("equipment", "설비", "Ref:Equipment"),
    _column("sdwt_prod", "소속"),
    _column("assignee", "담당자"),
    _column("status", "상태"),
    _column("priority", "우선순위"),
    _column("due_at", "기한", "DateTime:UTC"),
    _column("resolution", "완료 내용"),
    _column("reviewer", "검토자"),
    _column("completed_at", "완료 시각", "DateTime:UTC"),
    _column("archived", "보관", "Bool"),
]

WORKLOG_TASK_COLUMN = _column("task", "후속 Task", "Ref:Task")


def _find_named(items: list[dict[str, Any]], *, name: str) -> dict[str, Any] | None:
    """Grist 목록에서 name이 정확히 같은 항목을 반환합니다."""

    return next((item for item in items if str(item.get("name") or "") == name), None)


def _ensure_workspace(client: GristClient, *, name: str) -> tuple[int, list[dict[str, Any]]]:
    """이름이 같은 workspace와 기존 document 목록을 반환합니다."""

    workspaces = client.list_workspaces()
    workspace = _find_named(workspaces, name=name)
    if workspace:
        docs = workspace.get("docs", []) if isinstance(workspace.get("docs"), list) else []
        return int(workspace["id"]), [item for item in docs if isinstance(item, dict)]
    return client.create_workspace(name=name), []


def _ensure_document(
    client: GristClient,
    *,
    workspace_id: int,
    documents: list[dict[str, Any]],
    name: str,
) -> tuple[str, bool]:
    """이름이 같은 document를 재사용하고 없으면 생성합니다."""

    document = _find_named(documents, name=name)
    if document:
        doc_id = str(document.get("urlId") or document.get("id") or "").strip()
        if doc_id:
            return doc_id, False
    return client.create_document(workspace_id=workspace_id, name=name), True


def _ensure_table(
    client: GristClient,
    *,
    doc_id: str,
    table_id: str,
    columns: list[dict[str, Any]],
) -> None:
    """table과 column type 계약을 보장하고 잘못된 기존 type은 실패시킵니다."""

    table_ids = {str(item.get("id") or "") for item in client.list_tables(doc_id=doc_id)}
    if table_id not in table_ids:
        client.create_tables(
            doc_id=doc_id,
            tables=[{"id": table_id, "columns": columns}],
        )
        return

    existing_columns = client.list_columns(doc_id=doc_id, table_id=table_id)
    existing_by_id = {
        str(item.get("id") or ""): item
        for item in existing_columns
        if str(item.get("id") or "")
    }
    missing: list[dict[str, Any]] = []
    for definition in columns:
        column_id = str(definition["id"])
        existing = existing_by_id.get(column_id)
        if existing is None:
            missing.append(definition)
            continue
        fields = existing.get("fields") if isinstance(existing.get("fields"), dict) else {}
        actual_type = str(fields.get("type") or "Any")
        expected_type = str(definition["fields"]["type"])
        if actual_type != expected_type:
            raise GristDemoError(
                f"기존 Grist column type이 demo 계약과 다릅니다. "
                f"table={table_id} column={column_id} "
                f"actual={actual_type} expected={expected_type}"
            )
    if missing:
        client.create_columns(doc_id=doc_id, table_id=table_id, columns=missing)


def _ensure_schema(client: GristClient, *, doc_id: str, document_created: bool) -> None:
    """참조 순서에 맞게 Equipment, WorkLog, Task schema를 보장합니다."""

    _ensure_table(
        client,
        doc_id=doc_id,
        table_id="Equipment",
        columns=EQUIPMENT_COLUMNS,
    )
    _ensure_table(
        client,
        doc_id=doc_id,
        table_id="WorkLog",
        columns=WORKLOG_COLUMNS,
    )
    _ensure_table(
        client,
        doc_id=doc_id,
        table_id="Task",
        columns=TASK_COLUMNS,
    )
    _ensure_table(
        client,
        doc_id=doc_id,
        table_id="WorkLog",
        columns=[*WORKLOG_COLUMNS, WORKLOG_TASK_COLUMN],
    )
    if document_created:
        table_ids = {str(item.get("id") or "") for item in client.list_tables(doc_id=doc_id)}
        if "Table1" in table_ids:
            client.delete_table(doc_id=doc_id, table_id="Table1")


def _ensure_record(
    client: GristClient,
    *,
    doc_id: str,
    table_id: str,
    key_field: str,
    key_value: str,
    values: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    """기준키가 같은 record를 재사용하고 사용자 편집값을 덮어쓰지 않습니다."""

    existing = client.find_record_by_field(
        doc_id=doc_id,
        table_id=table_id,
        field_name=key_field,
        value=key_value,
    )
    if existing:
        return existing, False
    return (
        client.create_record(doc_id=doc_id, table_id=table_id, values=values),
        True,
    )


def _ensure_demo_records(
    client: GristClient,
    *,
    doc_id: str,
    user_sdwt_prod: str,
) -> tuple[int, int, int]:
    """설비 3건, 업무일지 3건, Task 2건과 참조 관계를 보장합니다."""

    today = date.today()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    equipment_specs = [
        ("DEV-EQP-01", "Etcher Alpha", "ETCH"),
        ("DEV-EQP-02", "Etcher Beta", "ETCH"),
        ("DEV-EQP-03", "Cleaner Gamma", "CLEAN"),
    ]
    equipment: dict[str, dict[str, Any]] = {}
    for equipment_id, name, process in equipment_specs:
        equipment[equipment_id], _created = _ensure_record(
            client,
            doc_id=doc_id,
            table_id="Equipment",
            key_field="equipment_id",
            key_value=equipment_id,
            values={
                "equipment_id": equipment_id,
                "line_id": "DEV-L1",
                "sdwt_prod": user_sdwt_prod,
                "prc_group": process,
                "equipment_name": name,
                "is_active": True,
                "source_updated_at": now.isoformat(),
                "archived": False,
            },
        )

    worklog_specs = [
        ("DEV-WL-001", "D", "챔버 온도 편차", True, "원인 점검 후 안정화"),
        ("DEV-WL-002", "N", "정기 세정 완료", False, "정상 완료"),
        ("DEV-WL-003", "D", "진공 도달 지연", True, "후속 leak 점검 필요"),
    ]
    worklogs: dict[str, dict[str, Any]] = {}
    equipment_keys = list(equipment)
    for index, (key, shift, symptom, follow_up, action) in enumerate(worklog_specs):
        equipment_row = equipment[equipment_keys[index]]
        worklogs[key], _created = _ensure_record(
            client,
            doc_id=doc_id,
            table_id="WorkLog",
            key_field="worklog_key",
            key_value=key,
            values={
                "worklog_key": key,
                "work_date": (today - timedelta(days=index)).isoformat(),
                "shift_code": shift,
                "occurred_at": (now - timedelta(hours=index * 8)).isoformat(),
                "equipment": int(equipment_row["id"]),
                "sdwt_prod": user_sdwt_prod,
                "writer": "Work Hub Dev",
                "symptom": symptom,
                "cause": "demo 원인",
                "action": action,
                "result": "모니터링 중" if follow_up else "완료",
                "status": "open" if follow_up else "done",
                "handover_required": follow_up,
                "follow_up_required": follow_up,
                "archived": False,
            },
        )

    task_specs = [
        ("DEV-TASK-001", "DEV-WL-001", "온도 편차 재점검"),
        ("DEV-TASK-002", "DEV-WL-003", "진공 leak 점검"),
    ]
    tasks: dict[str, dict[str, Any]] = {}
    for key, worklog_key, title in task_specs:
        worklog = worklogs[worklog_key]
        equipment_id = int(worklog.get("equipment") or 0)
        values = {
            "task_key": key,
            "title": title,
            "description": "다음 Shift에서 확인할 demo 조치사항",
            "source_worklog": int(worklog["id"]),
            "sdwt_prod": user_sdwt_prod,
            "assignee": "Work Hub Dev",
            "status": "open",
            "priority": "normal",
            "due_at": (now + timedelta(days=1)).isoformat(),
            "archived": False,
        }
        if equipment_id:
            values["equipment"] = equipment_id
        tasks[key], _created = _ensure_record(
            client,
            doc_id=doc_id,
            table_id="Task",
            key_field="task_key",
            key_value=key,
            values=values,
        )
        if not int(worklog.get("task") or 0):
            client.update_record(
                doc_id=doc_id,
                table_id="WorkLog",
                row_id=int(worklog["id"]),
                values={"task": int(tasks[key]["id"])},
            )

    return len(equipment), len(worklogs), len(tasks)


def _ensure_webhook(client: GristClient, *, doc_id: str) -> None:
    """callback URL이 설정된 환경에서 WorkLog Webhook을 원하는 상태로 맞춥니다."""

    callback_url = str(getattr(settings, "GRIST_WEBHOOK_CALLBACK_URL", "") or "").strip()
    token = build_grist_webhook_token(doc_id=doc_id, table_id="WorkLog")
    if not callback_url or not token:
        return
    name = "Portal WorkLog Task Sync"
    existing = client.list_webhooks(doc_id=doc_id)
    separator = "&" if "?" in callback_url else "?"
    url = (
        f"{callback_url}{separator}"
        f"{urlencode({'doc_id': doc_id, 'table_id': 'WorkLog'})}"
    )
    authorization = f"Bearer {token}"
    current = next(
        (
            item
            for item in existing
            if isinstance(item.get("fields"), dict)
            and str(item["fields"].get("name") or "") == name
        ),
        None,
    )
    if current is not None:
        fields = current["fields"]
        if fields.get("url") == url and fields.get("authorization") == authorization:
            return
        webhook_id = str(current.get("id") or "").strip()
        if not webhook_id:
            raise GristRequestError("기존 Grist Webhook ID가 없습니다.", retryable=False)
        client.update_webhook(
            doc_id=doc_id,
            webhook_id=webhook_id,
            url=url,
            authorization=authorization,
        )
        return
    client.create_webhook(
        doc_id=doc_id,
        name=name,
        table_id="WorkLog",
        url=url,
        authorization=authorization,
    )


def _worklog_launch_url(client: GristClient, *, doc_id: str) -> str:
    """WorkLog primary view를 바로 여는 외부 URL을 구성합니다."""

    worklog = next(
        (
            item
            for item in client.list_tables(doc_id=doc_id)
            if str(item.get("id") or "") == "WorkLog"
        ),
        None,
    )
    fields = worklog.get("fields") if isinstance(worklog, dict) else {}
    view_id = int(fields.get("primaryViewId") or 0) if isinstance(fields, dict) else 0
    public_url = str(getattr(settings, "GRIST_PUBLIC_URL", "") or "").rstrip("/")
    org = str(getattr(settings, "GRIST_ORG", "work-hub") or "work-hub").strip()
    base = f"{public_url}/o/{org}/doc/{doc_id}"
    return f"{base}/p/{view_id}" if view_id else base


def seed_grist_demo(
    *,
    user_sdwt_prod: str,
    client: GristClient | None = None,
    keycloak_client: Any = None,
) -> GristDemoResult:
    """로컬 Grist demo document·record·Webhook·Portal mapping을 멱등 생성합니다."""

    normalized_group = str(user_sdwt_prod or "").strip()
    if not normalized_group:
        raise GristDemoError("demo user_sdwt_prod가 필요합니다.")
    grist = client or GristClient.from_settings()
    try:
        workspace_id, documents = _ensure_workspace(grist, name="Work Hub Dev")
        doc_id, document_created = _ensure_document(
            grist,
            workspace_id=workspace_id,
            documents=documents,
            name=f"{normalized_group} 설비 업무일지",
        )
        _ensure_schema(grist, doc_id=doc_id, document_created=document_created)
        row_counts = _ensure_demo_records(
            grist,
            doc_id=doc_id,
            user_sdwt_prod=normalized_group,
        )
        _ensure_webhook(grist, doc_id=doc_id)
    except GristRequestError as exc:
        raise GristDemoError(str(exc)) from exc

    document_scope, mapping_created = configure_document_scope(
        keycloak_group_id=str(
            getattr(settings, "GRIST_DEV_KEYCLOAK_GROUP_ID", "")
            or f"dev-affiliation:{normalized_group}"
        ),
        affiliation_name=normalized_group,
        department="Development",
        line="DEV-L1",
        workspace_id=workspace_id,
        doc_id=doc_id,
        equipment_table_id="Equipment",
        worklog_table_id="WorkLog",
        task_table_id="Task",
        launch_url=_worklog_launch_url(grist, doc_id=doc_id),
        template_revision="grist-work-hub-v1-demo",
    )
    sync_document_access_scope(
        document_scope=document_scope,
        client=grist,
        keycloak_client=keycloak_client,
    )
    return GristDemoResult(
        workspace_id=workspace_id,
        doc_id=doc_id,
        equipment_table_id="Equipment",
        worklog_table_id="WorkLog",
        task_table_id="Task",
        equipment_rows=row_counts[0],
        worklog_rows=row_counts[1],
        task_rows=row_counts[2],
        mapping_created=mapping_created,
    )
