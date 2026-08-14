"""Work Hub context, 설비·권한 동기화, Webhook 멱등성 회귀 테스트입니다."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Lock
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch

from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.db import close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from api.account import selectors as account_selectors
from api.account import services as account_services

from .management.commands.audit_grist_schema import REQUIRED_COLUMNS
from .models import (
    GristAccessSyncOutbox,
    GristDocumentScope,
    GristTaskLink,
    GristWebhookReceipt,
)
from .services import (
    build_grist_webhook_token,
    build_work_hub_context,
    configure_document_scope,
    enqueue_access_sync_for_affiliations,
    enqueue_grist_webhook,
    process_access_sync_outbox_batch,
    process_grist_webhook_batch,
    prune_completed_access_sync_outbox,
    prune_completed_webhook_receipts,
    prune_failed_webhook_receipts,
    reconcile_all_document_access_scopes,
    seed_grist_demo,
    sync_document_access_scope,
    sync_equipment_scope,
)
from .services.client import (
    GristClient,
    GristConfigurationError,
    GristRequestError,
)
from .services.webhook import (
    _claim_next_webhook_receipt,
    _run_claimed_webhook_receipt,
)


GRIST_FORWARD_AUTH_TEST_SECRET = "test-grist-forward-auth-secret"


def _process_grist_webhook(
    *,
    doc_id: str,
    table_id: str,
    rows: list[dict],
    client=None,
) -> dict[str, object]:
    """테스트에서 queue 적재 후 실제 worker 처리 경로를 한 번 실행합니다."""

    queued = enqueue_grist_webhook(doc_id=doc_id, table_id=table_id, rows=rows)
    receipt = _claim_next_webhook_receipt()
    if receipt is None:
        return {
            "event_id": queued["event_id"],
            "duplicate": queued["duplicate"],
            "tasks_created": 0,
        }
    tasks_created = _run_claimed_webhook_receipt(receipt=receipt, client=client)
    return {
        "event_id": queued["event_id"],
        "duplicate": queued["duplicate"],
        "tasks_created": tasks_created,
    }


class FakeGristClient:
    """외부 통신 없이 Grist record와 provisioning 호출을 메모리에 기록합니다."""

    def __init__(self, *, rows=None) -> None:
        """고정 workspace와 table metadata, record 저장소를 준비합니다."""

        self.rows = list(rows or [])
        self.records: dict[str, list[dict]] = {
            "Equipment": [],
            "WorkLog": [],
            "Task": [],
        }
        self.created: list[tuple[str, str, dict]] = []
        self.updated: list[tuple[str, str, int, dict]] = []
        self.tables: dict[str, list[dict]] = {}
        self.workspaces = [{"id": 11, "name": "Work Hub Dev", "docs": []}]
        self.doc_id = "demo-doc"
        self.access = {
            "maxInheritedRole": None,
            "users": [
                {"email": "owner@example.invalid", "access": "owners"},
                {"email": "old@example.invalid", "access": "editors"},
            ]
        }
        self.access_changes: dict[str, str | None] = {}
        self.max_inherited_role_changes: list[str | None] = []
        self.webhooks: list[dict] = []

    def list_workspaces(self):
        """고정 workspace 목록을 반환합니다."""

        return self.workspaces

    def create_workspace(self, *, name: str):
        """고정 workspace ID를 반환합니다."""

        self.workspaces = [{"id": 11, "name": name, "docs": []}]
        return 11

    def create_document(self, *, workspace_id: int, name: str):
        """고정 document ID와 목록 항목을 생성합니다."""

        self.workspaces[0]["docs"].append({"id": self.doc_id, "name": name})
        self.tables[self.doc_id] = [
            {"id": "Table1", "fields": {"primaryViewId": 1}},
        ]
        return self.doc_id

    def list_tables(self, *, doc_id: str):
        """준비된 table metadata를 반환합니다."""

        return self.tables.get(doc_id, [])

    def create_tables(self, *, doc_id: str, tables: list[dict]):
        """table과 column을 메모리 metadata에 추가합니다."""

        target = self.tables.setdefault(doc_id, [])
        for definition in tables:
            target.append(
                {
                    "id": definition["id"],
                    "fields": {"primaryViewId": len(target) + 1},
                    "columns": list(definition.get("columns", [])),
                }
            )

    def delete_table(self, *, doc_id: str, table_id: str):
        """새 document의 기본 빈 table을 제거합니다."""

        self.tables[doc_id] = [
            item for item in self.tables.get(doc_id, []) if item["id"] != table_id
        ]

    def list_columns(self, *, doc_id: str, table_id: str):
        """table에 기록된 column 목록을 반환합니다."""

        table = next(item for item in self.tables.get(doc_id, []) if item["id"] == table_id)
        return list(table.get("columns", []))

    def create_columns(self, *, doc_id: str, table_id: str, columns: list[dict]):
        """table metadata에 누락 column을 추가합니다."""

        table = next(item for item in self.tables.get(doc_id, []) if item["id"] == table_id)
        table.setdefault("columns", []).extend(columns)

    def iter_records(self, *, doc_id: str, table_id: str):
        """설비 동기화 fixture 또는 table record를 반환합니다."""

        yield from (self.rows if self.rows else self.records.get(table_id, []))

    def find_record_by_field(
        self,
        *,
        doc_id: str,
        table_id: str,
        field_name: str,
        value: str,
    ):
        """기준 field가 같은 record를 반환합니다."""

        return next(
            (
                row
                for row in self.records.get(table_id, [])
                if str(row.get(field_name) or "") == str(value)
            ),
            None,
        )

    def create_record(self, *, doc_id: str, table_id: str, values: dict):
        """생성 호출을 기록하고 증가하는 ID를 반환합니다."""

        row = {
            "id": sum(len(items) for items in self.records.values()) + 101,
            **values,
        }
        self.records.setdefault(table_id, []).append(row)
        self.created.append((doc_id, table_id, dict(values)))
        return row

    def update_record(
        self,
        *,
        doc_id: str,
        table_id: str,
        row_id: int,
        values: dict,
    ):
        """수정 호출을 기록하고 메모리 record에 반영합니다."""

        self.updated.append((doc_id, table_id, row_id, dict(values)))
        for row in self.records.get(table_id, []):
            if int(row["id"]) == row_id:
                row.update(values)
                return row
        return {"id": row_id, **values}

    def get_document_access(self, *, doc_id: str):
        """준비된 document ACL을 반환합니다."""

        return self.access

    def update_document_access(
        self,
        *,
        doc_id: str,
        users: dict,
        max_inherited_role: str | None,
    ):
        """ACL 변경분과 상속 상한을 기록합니다."""

        self.access_changes.update(users)
        self.max_inherited_role_changes.append(max_inherited_role)

    def list_webhooks(self, *, doc_id: str):
        """준비된 Webhook 목록을 반환합니다."""

        return self.webhooks

    def create_webhook(self, **kwargs):
        """Webhook 생성 호출을 기록합니다."""

        self.webhooks.append(
            {
                "id": f"webhook-{len(self.webhooks) + 1}",
                "fields": dict(kwargs),
            }
        )

    def update_webhook(
        self,
        *,
        doc_id: str,
        webhook_id: str,
        url: str,
        authorization: str,
    ):
        """Webhook 수정 호출을 메모리 상태에 반영합니다."""

        webhook = next(item for item in self.webhooks if item["id"] == webhook_id)
        webhook["fields"].update(
            {
                "url": url,
                "authorization": authorization,
            }
        )


class BlockingFakeGristClient(FakeGristClient):
    """동일 Webhook의 첫 원격 조회를 멈춰 동시 전달을 재현합니다."""

    def __init__(self) -> None:
        """동시 조회 여부를 관찰할 event와 호출 잠금을 준비합니다."""

        super().__init__()
        self.first_find_entered = Event()
        self.concurrent_find_entered = Event()
        self.release_first_find = Event()
        self._find_lock = Lock()
        self._find_count = 0

    def find_record_by_field(self, **kwargs):
        """첫 조회 결과를 고정한 채 두 번째 호출 가능 여부를 관찰합니다."""

        with self._find_lock:
            self._find_count += 1
            call_number = self._find_count
        result = super().find_record_by_field(**kwargs)
        if call_number == 1:
            self.first_find_entered.set()
            if not self.release_first_find.wait(timeout=5):
                raise RuntimeError("첫 Grist 조회 대기 시간이 초과되었습니다.")
        else:
            self.concurrent_find_entered.set()
        return result


class TransactionObservingFakeGristClient(FakeGristClient):
    """Grist record 호출 시 DB transaction 활성 여부를 기록합니다."""

    def __init__(self) -> None:
        """호출별 transaction 상태 저장소를 준비합니다."""

        super().__init__()
        self.atomic_states: list[bool] = []

    def find_record_by_field(self, **kwargs):
        """원격 조회 시점의 transaction 상태를 기록합니다."""

        self.atomic_states.append(connection.in_atomic_block)
        return super().find_record_by_field(**kwargs)

    def create_record(self, **kwargs):
        """원격 생성 시점의 transaction 상태를 기록합니다."""

        self.atomic_states.append(connection.in_atomic_block)
        return super().create_record(**kwargs)

    def update_record(self, **kwargs):
        """원격 수정 시점의 transaction 상태를 기록합니다."""

        self.atomic_states.append(connection.in_atomic_block)
        return super().update_record(**kwargs)


@override_settings(
    WORK_HUB_ENABLED=True,
    GRIST_PUBLIC_URL="http://localhost:8100",
    GRIST_ORG="work-hub",
    GRIST_ALLOWED_LAUNCH_HOSTS=["localhost"],
    GRIST_WEBHOOK_CALLBACK_URL="",
    GRIST_ADMIN_EMAIL="owner@example.invalid",
)
class WorkHubServiceTests(TestCase):
    """Work Hub 핵심 서비스 규칙을 검증합니다."""

    def setUp(self) -> None:
        """현재 소속이 있는 일반 사용자와 Grist mapping을 준비합니다."""

        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="WH0001",
            password="password",
            email="member@example.invalid",
        )
        account_services.set_current_affiliation_for_user(
            user=self.user,
            department="ETCH",
            line="L1",
            user_sdwt_prod="SDWT-A",
        )
        self.affiliation = account_selectors.get_active_affiliation_by_user_sdwt_prod(
            user_sdwt_prod="SDWT-A",
        )
        self.access_admin = User.objects.create_superuser(
            sabun="WHACCESSADMIN",
            password="password",
        )
        for scope_key in ("portal", "work-hub"):
            _payload, status = account_services.decide_user_access(
                actor=self.access_admin,
                user_id=self.user.id,
                scope_key=scope_key,
                action="grant",
                reason="Work Hub 서비스 테스트 권한",
            )
            self.assertEqual(status, 200)
        self.scope = GristDocumentScope.objects.create(
            affiliation=self.affiliation,
            workspace_id=1,
            doc_id="doc-a",
            equipment_table_id="Equipment",
            worklog_table_id="WorkLog",
            task_table_id="Task",
            launch_url="http://localhost:8100/o/work-hub/doc/doc-a/p/3",
        )

    @override_settings(GRIST_WEBHOOK_SECRET="test-webhook-secret")
    def test_webhook_token_is_scoped_to_document_and_table(self) -> None:
        """Webhook token은 마스터 secret을 노출하지 않고 대상마다 달라집니다."""

        doc_a = build_grist_webhook_token(doc_id="doc-a", table_id="WorkLog")
        doc_b = build_grist_webhook_token(doc_id="doc-b", table_id="WorkLog")
        other_table = build_grist_webhook_token(doc_id="doc-a", table_id="Task")

        self.assertEqual(len(doc_a), 64)
        self.assertNotEqual(doc_a, "test-webhook-secret")
        self.assertEqual(len({doc_a, doc_b, other_table}), 3)

    def test_context_returns_only_current_group_for_member(self) -> None:
        """일반 사용자는 현재 소속의 단일 launcher만 받습니다."""

        payload = build_work_hub_context(user=self.user)

        self.assertTrue(payload["available"])
        self.assertEqual(payload["mode"], "single")
        self.assertEqual(payload["groups"][0]["user_sdwt_prod"], "SDWT-A")
        self.assertEqual(payload["groups"][0]["role"], "member")

    @override_settings(WORK_HUB_ENABLED=False)
    def test_context_feature_flag_disables_launcher(self) -> None:
        """기능 플래그가 꺼지면 mapping이 있어도 비활성 상태를 반환합니다."""

        payload = build_work_hub_context(user=self.user)

        self.assertFalse(payload["enabled"])
        self.assertEqual(payload["mode"], "disabled")
        self.assertEqual(payload["groups"], [])

    def test_superuser_can_switch_multiple_mapped_groups(self) -> None:
        """슈퍼유저는 manager로 활성 mapping 여러 개를 전환합니다."""

        second_user = get_user_model().objects.create_user(sabun="WH0002", password="password")
        account_services.set_current_affiliation_for_user(
            user=second_user,
            department="ETCH",
            line="L2",
            user_sdwt_prod="SDWT-B",
        )
        affiliation_b = account_selectors.get_active_affiliation_by_user_sdwt_prod(
            user_sdwt_prod="SDWT-B",
        )
        GristDocumentScope.objects.create(
            affiliation=affiliation_b,
            workspace_id=1,
            doc_id="doc-b",
            launch_url="http://localhost:8100/o/work-hub/doc/doc-b/p/3",
        )
        admin = get_user_model().objects.create_superuser(sabun="WHADMIN", password="password")

        payload = build_work_hub_context(user=admin)

        self.assertEqual(payload["mode"], "multiple")
        self.assertEqual({group["role"] for group in payload["groups"]}, {"manager"})

    def test_manager_context_and_grant_signal_follow_work_hub_data_scope(self) -> None:
        """manager도 앱별 grant가 없는 소속은 보지 못하고 grant 변경은 Outbox를 만듭니다."""

        account_services.ensure_self_access(self.user, role="manager")
        account_services.ensure_affiliation_option(
            department="PHOTO",
            line="L2",
            user_sdwt_prod="SDWT-B",
        )
        affiliation_b = account_selectors.get_active_affiliation_by_user_sdwt_prod(
            user_sdwt_prod="SDWT-B",
        )
        scope_b = GristDocumentScope.objects.create(
            affiliation=affiliation_b,
            workspace_id=1,
            doc_id="doc-b",
            launch_url="http://localhost:8100/o/work-hub/doc/doc-b/p/3",
        )
        _role_payload, role_status = account_services.grant_or_revoke_access(
            grantor=self.access_admin,
            target_group="SDWT-B",
            target_user=self.user,
            action="grant",
            role="viewer",
            reason="Work Hub launcher 범위 테스트",
        )
        self.assertEqual(role_status, 200)

        before_grant = build_work_hub_context(user=self.user)
        GristAccessSyncOutbox.objects.all().delete()
        grant_payload, grant_status = (
            account_services.update_user_scope_affiliation_data(
                actor=self.access_admin,
                user_id=self.user.id,
                scope_key="work-hub",
                data_scope_mode="default",
                affiliation_ids=[affiliation_b.id],
                reason="Work Hub B 소속 launcher 허용",
            )
        )
        after_grant = build_work_hub_context(user=self.user)

        self.assertEqual(grant_status, 200, grant_payload)
        self.assertEqual(
            [group["user_sdwt_prod"] for group in before_grant["groups"]],
            ["SDWT-A"],
        )
        self.assertEqual(
            {group["user_sdwt_prod"] for group in after_grant["groups"]},
            {"SDWT-A", "SDWT-B"},
        )
        self.assertTrue(
            GristAccessSyncOutbox.objects.filter(
                document_scope=scope_b,
                reason="scope_affiliation_grant_changed",
            ).exists()
        )

    @patch("api.work_hub.services.equipment.observer_selectors.list_equipments_for_user_sdwt_prod")
    def test_equipment_sync_upserts_and_archives_without_delete(self, equipment_selector) -> None:
        """설비 동기화는 신규 record를 만들고 원본 누락 record를 archive합니다."""

        equipment_selector.return_value = [
            {
                "equipment_id": "EQ-1",
                "line_id": "L1",
                "sdwt_prod": "SDWT-A",
                "prc_group": "P1",
                "equipment_name": "EQ-1",
            }
        ]
        client = FakeGristClient(rows=[{"id": 8, "equipment_id": "OLD", "archived": False}])

        result = sync_equipment_scope(document_scope=self.scope, client=client)

        self.assertEqual(result, {"created": 1, "updated": 0, "archived": 1, "unchanged": 0})
        self.assertEqual(client.created[0][2]["equipment_id"], "EQ-1")
        self.assertEqual(client.updated[0][1:3], ("Equipment", 8))
        self.assertTrue(client.updated[0][3]["archived"])

    def test_worklog_webhook_creates_one_task_and_is_idempotent(self) -> None:
        """같은 batch를 재처리해도 Task는 하나이고 지워진 참조는 복구합니다."""

        client = FakeGristClient()
        rows = [
            {
                "id": 77,
                "follow_up_required": True,
                "task": 0,
                "archived": False,
                "equipment": 2,
                "symptom": "온도 이상",
                "action": "원인 점검",
            }
        ]

        first = _process_grist_webhook(
            doc_id="doc-a",
            table_id="WorkLog",
            rows=rows,
            client=client,
        )
        second = _process_grist_webhook(
            doc_id="doc-a",
            table_id="WorkLog",
            rows=rows,
            client=client,
        )

        self.assertEqual(first["tasks_created"], 1)
        self.assertTrue(second["duplicate"])
        self.assertEqual(len(client.created), 1)
        self.assertEqual(client.created[0][2]["equipment"], 2)
        self.assertEqual(
            client.updated,
            [
                ("doc-a", "WorkLog", 77, {"task": 101}),
                ("doc-a", "WorkLog", 77, {"task": 101}),
            ],
        )
        self.assertEqual(GristTaskLink.objects.count(), 1)
        receipt = GristWebhookReceipt.objects.get()
        self.assertEqual(receipt.status, "done")
        self.assertEqual(receipt.attempt_count, 2)

    def test_enqueued_webhook_is_processed_by_worker_batch(self) -> None:
        """HTTP 경로가 적재한 receipt는 worker batch가 나중에 처리합니다."""

        client = FakeGristClient()
        rows = [
            {
                "id": 75,
                "follow_up_required": True,
                "task": 0,
                "archived": False,
                "symptom": "비동기 처리",
            }
        ]

        queued = enqueue_grist_webhook(
            doc_id="doc-a",
            table_id="WorkLog",
            rows=rows,
        )

        receipt = GristWebhookReceipt.objects.get(event_id=queued["event_id"])
        self.assertEqual(queued["status"], GristWebhookReceipt.Status.RECEIVED)
        self.assertEqual(receipt.payload["rows"], rows)
        self.assertEqual(receipt.attempt_count, 0)

        result = process_grist_webhook_batch(limit=1, client=client)

        receipt.refresh_from_db()
        self.assertEqual(result, {"processed": 1, "succeeded": 1, "failed": 0})
        self.assertEqual(receipt.status, GristWebhookReceipt.Status.DONE)
        self.assertEqual(receipt.attempt_count, 1)
        self.assertEqual(len(client.created), 1)

    def test_webhook_worker_recovers_expired_processing_lease(self) -> None:
        """중단된 worker의 처리 임대는 만료 후 다음 worker가 회수합니다."""

        queued = enqueue_grist_webhook(
            doc_id="doc-a",
            table_id="WorkLog",
            rows=[{"id": 74, "follow_up_required": False}],
        )
        GristWebhookReceipt.objects.filter(event_id=queued["event_id"]).update(
            status=GristWebhookReceipt.Status.PROCESSING,
            attempt_count=1,
            processed_at=timezone.now() - timedelta(minutes=3),
        )

        result = process_grist_webhook_batch(limit=1, client=FakeGristClient())

        receipt = GristWebhookReceipt.objects.get(event_id=queued["event_id"])
        self.assertEqual(result, {"processed": 1, "succeeded": 1, "failed": 0})
        self.assertEqual(receipt.status, GristWebhookReceipt.Status.DONE)
        self.assertEqual(receipt.attempt_count, 2)

    @patch("api.work_hub.services.webhook.GristClient.from_settings")
    def test_webhook_worker_marks_configuration_error_terminal(
        self,
        from_settings,
    ) -> None:
        """재시도해도 해결되지 않는 Grist 설정 오류는 terminal로 보존합니다."""

        from_settings.side_effect = GristConfigurationError("API key가 없습니다.")
        queued = enqueue_grist_webhook(
            doc_id="doc-a",
            table_id="WorkLog",
            rows=[{"id": 73, "follow_up_required": False}],
        )

        result = process_grist_webhook_batch(limit=1)

        receipt = GristWebhookReceipt.objects.get(event_id=queued["event_id"])
        self.assertEqual(result, {"processed": 1, "succeeded": 0, "failed": 1})
        self.assertEqual(receipt.status, GristWebhookReceipt.Status.TERMINAL)
        self.assertIn("GristConfigurationError", receipt.last_error)

    def test_worklog_webhook_retry_reuses_task_after_remote_update_failure(self) -> None:
        """WorkLog 연결 실패 뒤 재시도는 이미 만든 원격 Task를 재사용합니다."""

        client = FakeGristClient()
        original_update_record = client.update_record
        client.update_record = Mock(side_effect=RuntimeError("Grist unavailable"))
        rows = [
            {
                "id": 76,
                "follow_up_required": True,
                "task": 0,
                "archived": False,
                "symptom": "재시도 확인",
            }
        ]

        with self.assertRaisesMessage(RuntimeError, "Grist unavailable"):
            _process_grist_webhook(
                doc_id="doc-a",
                table_id="WorkLog",
                rows=rows,
                client=client,
            )

        failed_receipt = GristWebhookReceipt.objects.get()
        self.assertEqual(failed_receipt.status, GristWebhookReceipt.Status.FAILED)
        self.assertGreater(failed_receipt.available_at, timezone.now())
        self.assertFalse(GristTaskLink.objects.filter(worklog_row_id=76).exists())

        client.update_record = original_update_record
        retried = _process_grist_webhook(
            doc_id="doc-a",
            table_id="WorkLog",
            rows=rows,
            client=client,
        )

        failed_receipt.refresh_from_db()
        self.assertEqual(retried["tasks_created"], 0)
        self.assertEqual(len(client.created), 1)
        self.assertEqual(failed_receipt.status, GristWebhookReceipt.Status.DONE)
        self.assertEqual(failed_receipt.attempt_count, 2)
        self.assertEqual(
            GristTaskLink.objects.get(worklog_row_id=76).task_row_id,
            101,
        )

    def test_worklog_webhook_persists_maximum_length_task_key(self) -> None:
        """최대 document·table·row 식별자로 만든 Task key를 온전히 저장합니다."""

        doc_id = "d" * 128
        table_id = "t" * 64
        row_id = 9_223_372_036_854_775_807
        self.scope.doc_id = doc_id
        self.scope.worklog_table_id = table_id
        self.scope.save(update_fields=["doc_id", "worklog_table_id", "updated_at"])

        result = _process_grist_webhook(
            doc_id=doc_id,
            table_id=table_id,
            rows=[
                {
                    "id": row_id,
                    "follow_up_required": True,
                    "task": 0,
                    "archived": False,
                }
            ],
            client=FakeGristClient(),
        )

        expected_task_key = f"grist-worklog:{doc_id}:{table_id}:{row_id}"
        task_link = GristTaskLink.objects.get(worklog_row_id=row_id)
        self.assertEqual(result["tasks_created"], 1)
        self.assertEqual(len(expected_task_key), 227)
        self.assertEqual(task_link.task_key, expected_task_key)

    def test_work_hub_admin_models_are_read_only(self) -> None:
        """Admin은 서비스 불변조건을 우회하는 추가·수정·삭제 입력을 제공하지 않습니다."""

        request = Mock()
        for model in (
            GristDocumentScope,
            GristAccessSyncOutbox,
            GristWebhookReceipt,
            GristTaskLink,
        ):
            model_admin = django_admin.site._registry[model]
            concrete_fields = {field.name for field in model._meta.fields}

            self.assertFalse(model_admin.has_add_permission(request))
            self.assertFalse(model_admin.has_change_permission(request, Mock()))
            self.assertFalse(model_admin.has_delete_permission(request))
            self.assertEqual(
                set(model_admin.get_readonly_fields(request)),
                concrete_fields,
            )

    @patch("api.work_hub.management.commands.audit_grist_schema.GristClient.from_settings")
    def test_schema_audit_accepts_matching_column_types(self, from_settings) -> None:
        """schema 감사는 필수 column과 기대 type이 모두 맞으면 성공합니다."""

        client = FakeGristClient()
        client.tables["doc-a"] = []
        for table_name, table_id in (
            ("equipment", "Equipment"),
            ("worklog", "WorkLog"),
            ("task", "Task"),
        ):
            client.tables["doc-a"].append(
                {
                    "id": table_id,
                    "columns": [
                        {"id": column_id, "fields": {"type": column_type}}
                        for column_id, column_type in REQUIRED_COLUMNS[table_name].items()
                    ],
                }
            )
        from_settings.return_value = client

        call_command("audit_grist_schema", stdout=StringIO())

    @patch("api.work_hub.management.commands.audit_grist_schema.GristClient.from_settings")
    def test_schema_audit_rejects_wrong_column_type(self, from_settings) -> None:
        """필수 column이 있어도 type이 다르면 rollout 감사를 실패시킵니다."""

        client = FakeGristClient()
        client.tables["doc-a"] = []
        for table_name, table_id in (
            ("equipment", "Equipment"),
            ("worklog", "WorkLog"),
            ("task", "Task"),
        ):
            client.tables["doc-a"].append(
                {
                    "id": table_id,
                    "columns": [
                        {
                            "id": column_id,
                            "fields": {
                                "type": (
                                    "Text"
                                    if table_name == "worklog" and column_id == "task"
                                    else column_type
                                )
                            },
                        }
                        for column_id, column_type in REQUIRED_COLUMNS[table_name].items()
                    ],
                }
            )
        from_settings.return_value = client

        with self.assertRaisesMessage(
            CommandError,
            "task(type=Text, expected=Ref:Task)",
        ):
            call_command("audit_grist_schema", stdout=StringIO())

    def test_worklog_webhook_different_payload_for_same_row_reuses_task_link(self) -> None:
        """같은 WorkLog의 서로 다른 event도 잠긴 Task link를 재사용합니다."""

        client = FakeGristClient()
        first_rows = [
            {
                "id": 78,
                "follow_up_required": True,
                "task": 0,
                "archived": False,
                "symptom": "첫 이벤트",
            }
        ]
        second_rows = [{**first_rows[0], "symptom": "후속 이벤트"}]

        first = _process_grist_webhook(
            doc_id="doc-a",
            table_id="WorkLog",
            rows=first_rows,
            client=client,
        )
        second = _process_grist_webhook(
            doc_id="doc-a",
            table_id="WorkLog",
            rows=second_rows,
            client=client,
        )

        self.assertEqual(first["tasks_created"], 1)
        self.assertEqual(second["tasks_created"], 0)
        self.assertEqual(len(client.created), 1)
        self.assertEqual(GristTaskLink.objects.filter(worklog_row_id=78).count(), 1)

    def test_worklog_webhook_recreates_deleted_remote_task(self) -> None:
        """로컬 link가 가리키는 Task가 삭제되면 같은 key로 새 Task를 생성합니다."""

        client = FakeGristClient()
        rows = [
            {
                "id": 79,
                "follow_up_required": True,
                "task": 0,
                "archived": False,
                "symptom": "삭제 복구",
            }
        ]

        first = _process_grist_webhook(
            doc_id="doc-a",
            table_id="WorkLog",
            rows=rows,
            client=client,
        )
        client.records["Task"] = [
            {"id": 999, "task_key": "unrelated-task"},
        ]
        second = _process_grist_webhook(
            doc_id="doc-a",
            table_id="WorkLog",
            rows=rows,
            client=client,
        )

        task_link = GristTaskLink.objects.get(worklog_row_id=79)
        self.assertEqual(first["tasks_created"], 1)
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["tasks_created"], 1)
        self.assertEqual(len(client.created), 2)
        self.assertNotEqual(task_link.task_row_id, 101)
        self.assertEqual(client.updated[-1][3], {"task": task_link.task_row_id})

    def test_access_sync_reconciles_affiliation_roles(self) -> None:
        """현재 소속 역할은 Grist ACL이 되고 이전 일반 사용자 접근은 제거됩니다."""

        client = FakeGristClient()
        superuser_emails = {
            str(email).strip().lower()
            for email in get_user_model()
            .objects.filter(is_active=True, is_superuser=True)
            .exclude(email__isnull=True)
            .exclude(email="")
            .values_list("email", flat=True)
        }

        result = sync_document_access_scope(document_scope=self.scope, client=client)

        self.assertEqual(
            result,
            {
                "added": 1 + len(superuser_emails),
                "updated": 0,
                "removed": 1,
                "unchanged": 1,
            },
        )
        self.assertEqual(client.access_changes["member@example.invalid"], "editors")
        self.assertIsNone(client.access_changes["old@example.invalid"])
        self.assertNotIn("owner@example.invalid", client.access_changes)
        for email in superuser_emails:
            self.assertEqual(client.access_changes[email], "owners")

    @override_settings(GRIST_ADMIN_EMAIL="member@example.invalid")
    def test_access_sync_does_not_downgrade_configured_admin(self) -> None:
        """Portal 일반 구성원인 운영 관리자도 owner를 유지합니다."""

        client = FakeGristClient()
        client.access = {
            "maxInheritedRole": None,
            "users": [
                {"email": "member@example.invalid", "access": "owners"},
            ],
        }

        result = sync_document_access_scope(document_scope=self.scope, client=client)

        self.assertEqual(result["unchanged"], 1)
        self.assertNotIn("member@example.invalid", client.access_changes)

    @override_settings(GRIST_ADMIN_EMAIL="break-glass@example.invalid")
    def test_access_sync_adds_missing_configured_admin_as_owner(self) -> None:
        """운영 관리자가 document ACL에 없으면 owner로 추가합니다."""

        client = FakeGristClient()
        client.access = {
            "maxInheritedRole": None,
            "users": [
                {"email": "member@example.invalid", "access": "editors"},
            ],
        }

        sync_document_access_scope(document_scope=self.scope, client=client)

        self.assertEqual(client.access_changes["break-glass@example.invalid"], "owners")

    def test_access_sync_uses_batched_scope_queries_for_multiple_members(self) -> None:
        """문서 구성원이 늘어도 앱별 소속 판정 쿼리 수는 일정하게 유지됩니다."""

        for index in range(5):
            member = get_user_model().objects.create_user(
                sabun=f"WHBATCH{index}",
                password="password",
                email=f"batch-{index}@example.invalid",
            )
            account_services.set_current_affiliation_for_user(
                user=member,
                department="ETCH",
                line="L1",
                user_sdwt_prod="SDWT-A",
            )
            for scope_key in ("portal", "work-hub"):
                _payload, status = account_services.decide_user_access(
                    actor=self.access_admin,
                    user_id=member.id,
                    scope_key=scope_key,
                    action="grant",
                    reason="Work Hub batch ACL 테스트",
                )
                self.assertEqual(status, 200)
        GristAccessSyncOutbox.objects.all().delete()
        client = FakeGristClient()
        client.access = {"maxInheritedRole": None, "users": []}
        superuser_count = (
            get_user_model()
            .objects.filter(is_active=True, is_superuser=True)
            .exclude(email__isnull=True)
            .exclude(email="")
            .count()
        )

        with CaptureQueriesContext(connection) as queries:
            sync_document_access_scope(document_scope=self.scope, client=client)

        self.assertLessEqual(len(queries), 10)
        self.assertEqual(len(client.access_changes), 7 + superuser_count)

    def test_access_sync_includes_department_policy_member(self) -> None:
        """명시 권한 없이 부서 정책으로 승인된 사용자도 batch ACL에 포함합니다."""

        for scope_key in ("portal", "work-hub"):
            _reset_payload, reset_status = account_services.decide_user_access(
                actor=self.access_admin,
                user_id=self.user.id,
                scope_key=scope_key,
                action="reset_to_policy",
                reason="Work Hub 부서 정책 테스트",
            )
            self.assertEqual(reset_status, 200)
            _policy_payload, policy_status = account_services.create_access_policy_rule(
                actor=self.access_admin,
                scope_key=scope_key,
                rule_type="department",
                value="ETCH",
                is_active=True,
            )
            self.assertEqual(policy_status, 201)
        GristAccessSyncOutbox.objects.all().delete()
        client = FakeGristClient()
        client.access = {"maxInheritedRole": None, "users": []}

        sync_document_access_scope(document_scope=self.scope, client=client)

        self.assertEqual(
            client.access_changes["member@example.invalid"],
            "editors",
        )

    def test_access_sync_includes_unaffiliated_superuser_as_owner(self) -> None:
        """소속 구성원이 아닌 활성 superuser도 모든 document owner로 투영합니다."""

        get_user_model().objects.create_superuser(
            sabun="WHGLOBALADMIN",
            password="password",
            email="global.admin@example.invalid",
        )
        client = FakeGristClient()
        client.access = {"maxInheritedRole": None, "users": []}

        sync_document_access_scope(document_scope=self.scope, client=client)

        self.assertEqual(
            client.access_changes["global.admin@example.invalid"],
            "owners",
        )

    @patch("api.work_hub.services.access.logger.exception")
    @patch("api.work_hub.services.access.sync_document_access_scope")
    def test_periodic_access_reconciliation_continues_after_document_failure(
        self,
        sync_access,
        logger_exception,
    ) -> None:
        """정기 전체 ACL 동기화는 한 document 실패 후에도 다음 대상을 처리합니다."""

        account_services.ensure_affiliation_option(
            department="PHOTO",
            line="L2",
            user_sdwt_prod="SDWT-B",
        )
        affiliation_b = account_selectors.get_active_affiliation_by_user_sdwt_prod(
            user_sdwt_prod="SDWT-B",
        )
        GristDocumentScope.objects.create(
            affiliation=affiliation_b,
            workspace_id=2,
            doc_id="doc-b",
            launch_url="http://localhost:8100/o/work-hub/doc/doc-b/p/3",
        )
        sync_access.side_effect = [RuntimeError("doc-a unavailable"), {}]
        client = FakeGristClient()

        result = reconcile_all_document_access_scopes(client=client)

        self.assertEqual(result, {"processed": 2, "succeeded": 1, "failed": 1})
        self.assertEqual(sync_access.call_count, 2)
        logger_exception.assert_called_once()

    def test_superuser_creation_enqueues_all_document_access_sync(self) -> None:
        """소속 없는 superuser 생성도 모든 document ACL 동기화를 적재합니다."""

        GristAccessSyncOutbox.objects.all().delete()

        get_user_model().objects.create_superuser(
            sabun="WHQUEUEDADMIN",
            password="password",
            email="queued.admin@example.invalid",
        )

        item = GristAccessSyncOutbox.objects.get()
        self.assertEqual(item.document_scope, self.scope)
        self.assertEqual(item.reason, "user_identity_changed")

    def test_access_sync_requires_work_hub_scope_for_cross_affiliation_role(self) -> None:
        """다른 소속 역할은 Work Hub 앱별 grant가 있을 때만 Grist에 반영합니다."""

        viewer = get_user_model().objects.create_user(
            sabun="WH0003",
            password="password",
            email="viewer@example.invalid",
            knox_id="work-hub-viewer",
        )
        account_services.set_current_affiliation_for_user(
            user=viewer,
            department="PHOTO",
            line="L2",
            user_sdwt_prod="SDWT-B",
        )
        for scope_key in ("portal", "work-hub"):
            _payload, access_status = account_services.decide_user_access(
                actor=self.access_admin,
                user_id=viewer.id,
                scope_key=scope_key,
                action="grant",
                reason="Work Hub 교차 소속 테스트 권한",
            )
            self.assertEqual(access_status, 200)
        account_services.ensure_self_access(self.user, role="manager")
        _payload, status = account_services.grant_or_revoke_access(
            grantor=self.user,
            target_group="SDWT-A",
            target_user=viewer,
            action="grant",
            role="viewer",
            reason="Work Hub viewer 테스트",
        )
        denied_client = FakeGristClient()
        denied_client.access = {"users": []}

        sync_document_access_scope(document_scope=self.scope, client=denied_client)

        self.assertEqual(status, 200)
        self.assertNotIn("viewer@example.invalid", denied_client.access_changes)

        grant_payload, grant_status = (
            account_services.update_user_scope_affiliation_data(
                actor=self.access_admin,
                user_id=viewer.id,
                scope_key="work-hub",
                data_scope_mode="default",
                affiliation_ids=[self.affiliation.id],
                reason="Work Hub viewer 앱별 소속 범위",
            )
        )
        client = FakeGristClient()
        client.access = {"users": []}

        sync_document_access_scope(document_scope=self.scope, client=client)

        self.assertEqual(grant_status, 200, grant_payload)
        superuser_access = {
            str(email).strip().lower(): "owners"
            for email in get_user_model()
            .objects.filter(is_active=True, is_superuser=True)
            .exclude(email__isnull=True)
            .exclude(email="")
            .values_list("email", flat=True)
        }
        self.assertEqual(
            client.access_changes,
            superuser_access
            | {
                "member@example.invalid": "owners",
                "owner@example.invalid": "owners",
                "viewer@example.invalid": "viewers",
            },
        )

    def test_access_sync_removes_grist_public_accounts(self) -> None:
        """Portal desired state에 없는 Grist 공개 계정은 명시적으로 회수합니다."""

        client = FakeGristClient()
        client.access = {
            "maxInheritedRole": None,
            "users": [
                {"email": "owner@example.invalid", "access": "owners"},
                {"email": "anon@getgrist.com", "access": "viewers"},
                {"email": "everyone@getgrist.com", "access": "editors"},
                {"email": "previewer@getgrist.com", "access": "viewers"},
            ],
        }

        result = sync_document_access_scope(document_scope=self.scope, client=client)

        self.assertEqual(result["removed"], 3)
        self.assertNotIn("owner@example.invalid", client.access_changes)
        for email in (
            "anon@getgrist.com",
            "everyone@getgrist.com",
            "previewer@getgrist.com",
        ):
            self.assertIsNone(client.access_changes[email])

    def test_work_hub_access_revocation_removes_existing_grist_acl(self) -> None:
        """Work Hub 앱 권한 회수는 Outbox를 만들고 기존 document ACL을 제거합니다."""

        _payload, status = account_services.decide_user_access(
            actor=self.access_admin,
            user_id=self.user.id,
            scope_key="work-hub",
            action="revoke",
            reason="Work Hub 접근 회수 테스트",
        )
        client = FakeGristClient()
        client.access = {
            "maxInheritedRole": None,
            "users": [
                {"email": "member@example.invalid", "access": "editors"},
                {"email": "owner@example.invalid", "access": "owners"},
            ],
        }

        result = sync_document_access_scope(document_scope=self.scope, client=client)

        self.assertEqual(status, 200)
        self.assertEqual(result["removed"], 1)
        self.assertIsNone(client.access_changes["member@example.invalid"])
        self.assertTrue(
            GristAccessSyncOutbox.objects.filter(
                document_scope=self.scope,
                reason="app_access_changed",
            ).exists()
        )

    def test_access_sync_disables_inheritance_and_pins_desired_roles(self) -> None:
        """상위 ACL은 차단하고 Portal 사용자와 운영 관리자는 명시 권한으로 고정합니다."""

        client = FakeGristClient()
        client.access = {
            "maxInheritedRole": "owners",
            "users": [
                {
                    "email": "member@example.invalid",
                    "access": "editors",
                    "parentAccess": "editors",
                },
                {
                    "email": "owner@example.invalid",
                    "access": "owners",
                    "parentAccess": "owners",
                },
                {
                    "email": "inherited@example.invalid",
                    "access": "viewers",
                    "parentAccess": "viewers",
                },
            ],
        }

        sync_document_access_scope(document_scope=self.scope, client=client)

        self.assertEqual(client.max_inherited_role_changes, [None])
        self.assertEqual(client.access_changes["member@example.invalid"], "editors")
        self.assertEqual(client.access_changes["owner@example.invalid"], "owners")
        self.assertIsNone(client.access_changes["inherited@example.invalid"])

    def test_current_affiliation_change_enqueues_previous_and_new_documents(self) -> None:
        """소속 변경은 이전 document 회수와 신규 document 부여 작업을 함께 적재합니다."""

        account_services.ensure_affiliation_option(
            department="PHOTO",
            line="L2",
            user_sdwt_prod="SDWT-B",
        )
        affiliation_b = account_selectors.get_active_affiliation_by_user_sdwt_prod(
            user_sdwt_prod="SDWT-B"
        )
        GristDocumentScope.objects.create(
            affiliation=affiliation_b,
            workspace_id=1,
            doc_id="doc-b",
            launch_url="http://localhost:8100/o/work-hub/doc/doc-b/p/3",
        )

        account_services.set_current_affiliation_for_user(
            user=self.user,
            department="PHOTO",
            line="L2",
            user_sdwt_prod="SDWT-B",
        )

        self.assertEqual(
            set(
                GristAccessSyncOutbox.objects.values_list(
                    "document_scope__doc_id", flat=True
                )
            ),
            {"doc-a", "doc-b"},
        )

    @patch("api.work_hub.services.access.GristClient.from_settings")
    def test_access_outbox_processes_desired_state(self, from_settings) -> None:
        """Outbox worker는 Portal desired state를 적용하고 완료 상태를 기록합니다."""

        client = FakeGristClient()
        from_settings.return_value = client
        enqueue_access_sync_for_affiliations(
            affiliation_ids=[self.affiliation.id],
        )

        result = process_access_sync_outbox_batch(limit=10)

        self.assertEqual(result, {"processed": 1, "succeeded": 1, "failed": 0})
        self.assertEqual(
            GristAccessSyncOutbox.objects.get().status,
            GristAccessSyncOutbox.Status.DONE,
        )

    @patch("api.work_hub.services.access.logger.exception")
    @patch("api.work_hub.services.access.GristClient.from_settings")
    def test_access_outbox_retains_failure_for_retry(
        self, from_settings, logger_exception
    ) -> None:
        """Grist 장애는 Portal 변경을 되돌리지 않고 Outbox 재시도로 남깁니다."""

        client = FakeGristClient()
        client.get_document_access = Mock(side_effect=RuntimeError("Grist unavailable"))
        from_settings.return_value = client
        enqueue_access_sync_for_affiliations(
            affiliation_ids=[self.affiliation.id],
        )

        result = process_access_sync_outbox_batch(limit=10)

        item = GristAccessSyncOutbox.objects.get()
        self.assertEqual(result, {"processed": 1, "succeeded": 0, "failed": 1})
        self.assertEqual(item.status, GristAccessSyncOutbox.Status.FAILED)
        self.assertEqual(item.retry_count, 1)
        self.assertIn("Grist unavailable", item.last_error)
        logger_exception.assert_called_once()

    @patch("api.work_hub.services.access.logger.exception")
    @patch("api.work_hub.services.access.GristClient.from_settings")
    def test_access_outbox_stops_retrying_permanent_failure(
        self, from_settings, logger_exception
    ) -> None:
        """재시도 불가능한 Grist 오류는 terminal 상태로 보존합니다."""

        client = FakeGristClient()
        client.get_document_access = Mock(
            side_effect=GristRequestError("document not found", retryable=False)
        )
        from_settings.return_value = client
        enqueue_access_sync_for_affiliations(
            affiliation_ids=[self.affiliation.id],
        )

        first = process_access_sync_outbox_batch(limit=10)
        second = process_access_sync_outbox_batch(limit=10)

        item = GristAccessSyncOutbox.objects.get()
        self.assertEqual(first, {"processed": 1, "succeeded": 0, "failed": 1})
        self.assertEqual(second, {"processed": 0, "succeeded": 0, "failed": 0})
        self.assertEqual(item.status, GristAccessSyncOutbox.Status.TERMINAL)
        self.assertEqual(item.retry_count, 1)
        logger_exception.assert_called_once()

    @patch("api.work_hub.services.access.GristClient.from_settings")
    def test_access_enqueue_never_calls_grist_in_request_commit(
        self,
        from_settings,
    ) -> None:
        """Outbox 적재 transaction이 commit되어도 요청 경로에서 Grist를 호출하지 않습니다."""

        with self.captureOnCommitCallbacks(execute=True):
            queued = enqueue_access_sync_for_affiliations(
                affiliation_ids=[self.affiliation.id],
            )

        self.assertEqual(queued, 1)
        self.assertEqual(
            GristAccessSyncOutbox.objects.get().status,
            GristAccessSyncOutbox.Status.PENDING,
        )
        from_settings.assert_not_called()

    def test_configure_document_scope_enqueues_initial_access_sync(self) -> None:
        """신규 mapping은 같은 transaction에서 현재 document ACL Outbox를 적재합니다."""

        self.scope.delete()

        document_scope, created = configure_document_scope(
            user_sdwt_prod="SDWT-A",
            workspace_id=2,
            doc_id="doc-configured",
            equipment_table_id="Equipment",
            worklog_table_id="WorkLog",
            task_table_id="Task",
            launch_url="http://localhost:8100/o/work-hub/doc/doc-configured/p/3",
        )

        item = GristAccessSyncOutbox.objects.get()
        self.assertTrue(created)
        self.assertEqual(item.document_scope, document_scope)
        self.assertEqual(item.reason, "document_scope_configured")

    def test_configure_document_scope_rejects_doc_id_replacement(self) -> None:
        """기존 mapping의 document 교체를 막아 이전 ACL이 추적 밖에 남지 않게 합니다."""

        with self.assertRaisesMessage(ValidationError, "doc_id는 변경할 수 없습니다"):
            configure_document_scope(
                user_sdwt_prod="SDWT-A",
                workspace_id=2,
                doc_id="replacement-doc",
                equipment_table_id="Equipment",
                worklog_table_id="WorkLog",
                task_table_id="Task",
                launch_url="http://localhost:8100/o/work-hub/doc/replacement-doc/p/3",
            )

        self.scope.refresh_from_db()
        self.assertEqual(self.scope.doc_id, "doc-a")
        self.assertFalse(GristAccessSyncOutbox.objects.exists())

    @override_settings(GRIST_WEBHOOK_SECRET="test-webhook-secret")
    def test_configure_command_can_show_scoped_webhook_authorization(self) -> None:
        """운영 mapping 명령은 요청할 때만 document 전용 Authorization을 출력합니다."""

        stdout = StringIO()

        call_command(
            "configure_grist_scope",
            "--user-sdwt-prod",
            "SDWT-A",
            "--workspace-id",
            "1",
            "--doc-id",
            "doc-a",
            "--launch-url",
            "http://localhost:8100/o/work-hub/doc/doc-a/p/3",
            "--show-webhook-authorization",
            stdout=stdout,
        )

        token = build_grist_webhook_token(doc_id="doc-a", table_id="WorkLog")
        self.assertIn(f"Webhook Authorization: Bearer {token}", stdout.getvalue())

    def test_access_outbox_prunes_only_expired_done_history(self) -> None:
        """보존 기간이 지난 완료 이력만 삭제하고 실패·최근 이력은 유지합니다."""

        old_done = GristAccessSyncOutbox.objects.create(
            document_scope=self.scope,
            status=GristAccessSyncOutbox.Status.DONE,
            processed_at=timezone.now() - timedelta(days=31),
        )
        recent_done = GristAccessSyncOutbox.objects.create(
            document_scope=self.scope,
            status=GristAccessSyncOutbox.Status.DONE,
            processed_at=timezone.now() - timedelta(days=2),
        )
        old_failed = GristAccessSyncOutbox.objects.create(
            document_scope=self.scope,
            status=GristAccessSyncOutbox.Status.FAILED,
            processed_at=timezone.now() - timedelta(days=31),
        )

        deleted = prune_completed_access_sync_outbox(retention_days=30)

        self.assertEqual(deleted, 1)
        self.assertFalse(GristAccessSyncOutbox.objects.filter(id=old_done.id).exists())
        self.assertTrue(GristAccessSyncOutbox.objects.filter(id=recent_done.id).exists())
        self.assertTrue(GristAccessSyncOutbox.objects.filter(id=old_failed.id).exists())

    def test_webhook_receipt_prunes_only_expired_done_history(self) -> None:
        """보존 기간이 지난 완료 receipt만 삭제하고 실패·최근 이력은 유지합니다."""

        old_done = GristWebhookReceipt.objects.create(
            event_id="grist:old-done",
            doc_id="doc-a",
            table_id="WorkLog",
            payload_hash="old-done",
            status=GristWebhookReceipt.Status.DONE,
            processed_at=timezone.now() - timedelta(days=31),
        )
        recent_done = GristWebhookReceipt.objects.create(
            event_id="grist:recent-done",
            doc_id="doc-a",
            table_id="WorkLog",
            payload_hash="recent-done",
            status=GristWebhookReceipt.Status.DONE,
            processed_at=timezone.now() - timedelta(days=2),
        )
        old_failed = GristWebhookReceipt.objects.create(
            event_id="grist:old-failed",
            doc_id="doc-a",
            table_id="WorkLog",
            payload_hash="old-failed",
            status=GristWebhookReceipt.Status.FAILED,
            processed_at=timezone.now() - timedelta(days=31),
        )

        deleted = prune_completed_webhook_receipts(retention_days=30)

        self.assertEqual(deleted, 1)
        self.assertFalse(GristWebhookReceipt.objects.filter(id=old_done.id).exists())
        self.assertTrue(GristWebhookReceipt.objects.filter(id=recent_done.id).exists())
        self.assertTrue(GristWebhookReceipt.objects.filter(id=old_failed.id).exists())

    def test_webhook_receipt_prunes_expired_failed_history(self) -> None:
        """마지막 실패 후 보존 기간이 지난 receipt만 삭제합니다."""

        expired_failed = GristWebhookReceipt.objects.create(
            event_id="grist:expired-failed",
            doc_id="doc-a",
            table_id="WorkLog",
            payload_hash="expired-failed",
            status=GristWebhookReceipt.Status.FAILED,
            processed_at=timezone.now() - timedelta(days=91),
        )
        retained_failed = GristWebhookReceipt.objects.create(
            event_id="grist:retained-failed",
            doc_id="doc-a",
            table_id="WorkLog",
            payload_hash="retained-failed",
            status=GristWebhookReceipt.Status.FAILED,
            processed_at=timezone.now() - timedelta(days=30),
        )

        deleted = prune_failed_webhook_receipts(retention_days=90)

        self.assertEqual(deleted, 1)
        self.assertFalse(
            GristWebhookReceipt.objects.filter(id=expired_failed.id).exists()
        )
        self.assertTrue(
            GristWebhookReceipt.objects.filter(id=retained_failed.id).exists()
        )

    def test_user_deactivation_enqueues_current_document(self) -> None:
        """Portal 사용자 비활성화는 현재 document 권한 회수 작업을 적재합니다."""

        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        item = GristAccessSyncOutbox.objects.get()
        self.assertEqual(item.document_scope, self.scope)
        self.assertEqual(item.reason, "user_identity_changed")

    def test_affiliation_deactivation_enqueues_document_access_revocation(self) -> None:
        """소속 비활성화도 해당 document를 전체 동기화 대상에서 누락하지 않습니다."""

        self.affiliation.is_active = False
        self.affiliation.save(update_fields=["is_active"])

        item = GristAccessSyncOutbox.objects.get()
        self.assertEqual(item.document_scope, self.scope)
        self.assertEqual(item.reason, "affiliation_changed")

    @patch(
        "api.work_hub.management.commands.sync_grist_access."
        "sync_document_access_scope"
    )
    def test_manual_access_reconciliation_includes_inactive_affiliation(
        self,
        sync_access,
    ) -> None:
        """수동 전체 동기화는 비활성 소속 mapping도 ACL 회수 대상으로 포함합니다."""

        sync_access.return_value = {
            "added": 0,
            "updated": 0,
            "removed": 1,
            "unchanged": 0,
        }
        self.affiliation.is_active = False
        self.affiliation.save(update_fields=["is_active"])

        call_command(
            "sync_grist_access",
            "--all",
            "--dry-run",
            stdout=StringIO(),
        )

        sync_access.assert_called_once()
        self.assertEqual(
            sync_access.call_args.kwargs["document_scope"],
            self.scope,
        )

    @patch(
        "api.work_hub.management.commands.process_grist_access_sync."
        "process_grist_webhook_batch"
    )
    @patch(
        "api.work_hub.management.commands.process_grist_access_sync."
        "process_access_sync_outbox_batch"
    )
    @patch(
        "api.work_hub.management.commands.process_grist_access_sync."
        "reconcile_all_document_access_scopes"
    )
    @patch(
        "api.work_hub.management.commands.process_grist_access_sync."
        "prune_failed_webhook_receipts"
    )
    @patch(
        "api.work_hub.management.commands.process_grist_access_sync."
        "prune_completed_webhook_receipts"
    )
    @patch(
        "api.work_hub.management.commands.process_grist_access_sync."
        "prune_completed_access_sync_outbox"
    )
    @patch(
        "api.work_hub.management.commands.process_grist_access_sync."
        "account_services.deactivate_expired_scope_affiliation_grants"
    )
    def test_access_worker_deactivates_expired_grants_before_outbox(
        self,
        deactivate_expired,
        prune_outbox,
        prune_webhooks,
        prune_failed_webhooks,
        reconcile_access,
        process_outbox,
        process_webhooks,
    ) -> None:
        """worker는 매 처리 주기마다 Work Hub 만료 grant를 먼저 회수합니다."""

        deactivate_expired.return_value = 1
        prune_outbox.return_value = 2
        prune_webhooks.return_value = 3
        prune_failed_webhooks.return_value = 4
        reconcile_access.return_value = {
            "processed": 1,
            "succeeded": 1,
            "failed": 0,
        }
        process_outbox.return_value = {
            "processed": 1,
            "succeeded": 1,
            "failed": 0,
        }
        process_webhooks.return_value = {
            "processed": 1,
            "succeeded": 1,
            "failed": 0,
        }

        call_command(
            "process_grist_access_sync",
            "--limit",
            "7",
            "--webhook-limit",
            "5",
            "--expire-limit",
            "3",
            "--retention-days",
            "14",
            "--webhook-retention-days",
            "21",
            "--failed-webhook-retention-days",
            "45",
            "--prune-interval-seconds",
            "60",
            stdout=StringIO(),
        )

        deactivate_expired.assert_called_once_with(
            scope_key="work-hub",
            limit=3,
        )
        prune_outbox.assert_called_once_with(retention_days=14)
        prune_webhooks.assert_called_once_with(retention_days=21)
        prune_failed_webhooks.assert_called_once_with(retention_days=45)
        reconcile_access.assert_called_once_with()
        process_outbox.assert_called_once_with(limit=7)
        process_webhooks.assert_called_once_with(limit=5)

    @override_settings(WORK_HUB_ENABLED=False)
    @patch(
        "api.work_hub.management.commands.process_grist_access_sync."
        "process_grist_webhook_batch"
    )
    @patch(
        "api.work_hub.management.commands.process_grist_access_sync."
        "process_access_sync_outbox_batch"
    )
    @patch(
        "api.work_hub.management.commands.process_grist_access_sync."
        "reconcile_all_document_access_scopes"
    )
    def test_disabled_access_worker_skips_grist_writes(
        self,
        reconcile_access,
        process_outbox,
        process_webhooks,
    ) -> None:
        """기능을 끄면 worker는 전체·Outbox Grist 쓰기를 모두 건너뜁니다."""

        call_command(
            "process_grist_access_sync",
            stdout=StringIO(),
        )

        reconcile_access.assert_not_called()
        process_outbox.assert_not_called()
        process_webhooks.assert_not_called()

    @override_settings(
        GRIST_WEBHOOK_CALLBACK_URL="http://api:8000/api/v1/work-hub/webhooks/grist",
        GRIST_WEBHOOK_SECRET="test-webhook-secret",
    )
    def test_demo_seed_creates_records_and_mapping_idempotently(self) -> None:
        """빈 초기 상태에서 demo seed를 재실행해도 record와 mapping을 늘리지 않습니다."""

        client = FakeGristClient()
        self.scope.delete()

        first = seed_grist_demo(user_sdwt_prod="SDWT-A", client=client)
        second = seed_grist_demo(user_sdwt_prod="SDWT-A", client=client)

        document_scope = GristDocumentScope.objects.get(affiliation=self.affiliation)
        self.assertEqual(sum(len(items) for items in client.records.values()), 8)
        self.assertEqual((first.equipment_rows, first.worklog_rows, first.task_rows), (3, 3, 2))
        self.assertTrue(first.mapping_created)
        self.assertFalse(second.mapping_created)
        self.assertEqual(document_scope.doc_id, "demo-doc")
        self.assertEqual(document_scope.worklog_table_id, "WorkLog")
        self.assertEqual(len(client.webhooks), 1)
        authorization = client.webhooks[0]["fields"]["authorization"]
        self.assertNotEqual(authorization, "Bearer test-webhook-secret")

        client.webhooks[0]["fields"]["authorization"] = "Bearer stale-secret"
        seed_grist_demo(user_sdwt_prod="SDWT-A", client=client)

        self.assertEqual(len(client.webhooks), 1)
        self.assertEqual(
            client.webhooks[0]["fields"]["authorization"],
            authorization,
        )

    @override_settings(
        GRIST_API_URL="http://grist:8484/o/work-hub",
        GRIST_API_KEY="",
        GRIST_API_KEY_FILE="",
    )
    def test_client_requires_api_key_without_boot_fallback(self) -> None:
        """server-to-server 호출은 boot session 없이 명시 API key를 요구합니다."""

        with self.assertRaises(GristConfigurationError):
            GristClient.from_settings()

    def test_client_reads_bootstrapped_api_key_file(self) -> None:
        """환경 key가 비어 있으면 bootstrap이 만든 key 파일을 읽습니다."""

        with TemporaryDirectory() as temporary_directory:
            api_key_file = Path(temporary_directory) / "grist_api_key"
            api_key_file.write_text("bootstrapped-api-key\n", encoding="utf-8")
            with self.settings(
                GRIST_API_URL="http://grist:8484/o/work-hub",
                GRIST_API_KEY="",
                GRIST_API_KEY_FILE=str(api_key_file),
            ):
                client = GristClient.from_settings()

        self.assertEqual(client.api_key, "bootstrapped-api-key")

    def test_client_updates_webhook_with_grist_patch_contract(self) -> None:
        """Webhook 수정은 Grist 1.7.13이 요구하는 평탄한 PATCH body를 사용합니다."""

        response = Mock(status_code=200, content=b'{}')
        response.json.return_value = {}
        session = Mock()
        session.request.return_value = response
        client = GristClient(
            base_url="http://grist:8484/o/work-hub",
            api_key="test-api-key",
            connect_timeout=3.0,
            read_timeout=15.0,
            session=session,
        )

        client.update_webhook(
            doc_id="doc-a",
            webhook_id="webhook-1",
            url="http://api:8000/webhook?doc_id=doc-a",
            authorization="Bearer scoped-token",
        )

        self.assertEqual(
            session.request.call_args.kwargs["json"],
            {
                "url": "http://api:8000/webhook?doc_id=doc-a",
                "authorization": "Bearer scoped-token",
            },
        )

    def test_client_finds_record_with_server_side_filter(self) -> None:
        """기준 field 조회는 전체 table 대신 Grist filter query를 사용해야 합니다."""

        response = Mock(
            status_code=200,
            content=b'{"records":[{"id":17,"fields":{"task_key":"task-a"}}]}',
        )
        response.json.return_value = {
            "records": [
                {
                    "id": 17,
                    "fields": {"task_key": "task-a"},
                }
            ]
        }
        session = Mock()
        session.request.return_value = response
        client = GristClient(
            base_url="http://grist:8484/o/work-hub",
            api_key="test-api-key",
            connect_timeout=3.0,
            read_timeout=15.0,
            session=session,
        )

        record = client.find_record_by_field(
            doc_id="doc-a",
            table_id="Task",
            field_name="task_key",
            value="task-a",
        )

        self.assertEqual(record, {"id": 17, "task_key": "task-a"})
        self.assertEqual(
            session.request.call_args.kwargs["params"],
            {"filter": '{"task_key":["task-a"]}'},
        )


@override_settings(
    WORK_HUB_ENABLED=True,
    GRIST_PUBLIC_URL="http://localhost:8100",
    GRIST_ADMIN_EMAIL="owner@example.invalid",
)
class WorkHubWebhookConcurrencyTests(TransactionTestCase):
    """Webhook의 짧은 transaction 경계와 동시 처리를 검증합니다."""

    serialized_rollback = True

    def _fixture_teardown(self) -> None:
        """flush 뒤 data migration 초기값을 복원해 후속 테스트를 격리합니다."""

        super()._fixture_teardown()
        for database_name in self._databases_names(include_mirrors=False):
            database_connection = connections[database_name]
            serialized_contents = getattr(
                database_connection,
                "_test_serialized_contents",
                None,
            )
            if serialized_contents:
                database_connection.creation.deserialize_db_from_string(
                    serialized_contents
                )

    def setUp(self) -> None:
        """동시 요청 스레드가 조회할 Portal 사용자와 document를 준비합니다."""

        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="WHCONCURRENT",
            password="password",
            email="concurrent@example.invalid",
        )
        account_services.set_current_affiliation_for_user(
            user=self.user,
            department="ETCH",
            line="L1",
            user_sdwt_prod="SDWT-CONCURRENT",
        )
        affiliation = account_selectors.get_active_affiliation_by_user_sdwt_prod(
            user_sdwt_prod="SDWT-CONCURRENT"
        )
        GristDocumentScope.objects.create(
            affiliation=affiliation,
            workspace_id=1,
            doc_id="doc-concurrent",
            worklog_table_id="WorkLog",
            task_table_id="Task",
            launch_url="http://localhost:8100/o/work-hub/doc/doc-concurrent/p/3",
        )

    @staticmethod
    def _process_in_thread(*, client: BlockingFakeGristClient, rows: list[dict]):
        """스레드별 DB connection으로 동일 Webhook 서비스를 호출합니다."""

        close_old_connections()
        try:
            return _process_grist_webhook(
                doc_id="doc-concurrent",
                table_id="WorkLog",
                rows=rows,
                client=client,
            )
        finally:
            close_old_connections()

    def test_concurrent_identical_webhooks_create_one_task(self) -> None:
        """동일 payload가 겹치면 두 번째 호출은 기다리지 않고 중복 접수됩니다."""

        client = BlockingFakeGristClient()
        rows = [
            {
                "id": 91,
                "follow_up_required": True,
                "task": 0,
                "archived": False,
                "symptom": "동시 이벤트",
            }
        ]
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(self._process_in_thread, client=client, rows=rows)
            self.assertTrue(client.first_find_entered.wait(timeout=3))
            second = executor.submit(self._process_in_thread, client=client, rows=rows)
            self.assertFalse(client.concurrent_find_entered.wait(timeout=1))
            second_result = second.result(timeout=1)
            self.assertTrue(second_result["duplicate"])
            client.release_first_find.set()
            results = [first.result(timeout=5), second_result]

        self.assertEqual(len(client.created), 1)
        self.assertEqual(GristTaskLink.objects.filter(worklog_row_id=91).count(), 1)
        self.assertEqual(
            sorted(result["duplicate"] for result in results),
            [False, True],
        )

    def test_grist_record_calls_run_outside_database_transaction(self) -> None:
        """느린 Grist record 호출은 DB transaction 밖에서 실행됩니다."""

        client = TransactionObservingFakeGristClient()

        result = _process_grist_webhook(
            doc_id="doc-concurrent",
            table_id="WorkLog",
            rows=[
                {
                    "id": 92,
                    "follow_up_required": True,
                    "task": 0,
                    "archived": False,
                    "symptom": "transaction 경계",
                }
            ],
            client=client,
        )

        self.assertEqual(result["tasks_created"], 1)
        self.assertEqual(client.atomic_states, [False, False, False])


@override_settings(
    WORK_HUB_ENABLED=True,
    GRIST_WEBHOOK_SECRET="test-webhook-secret",
    GRIST_PUBLIC_URL="http://grist.example.invalid",
    GRIST_FORWARD_AUTH_TICKET_SECRET=GRIST_FORWARD_AUTH_TEST_SECRET,
    GRIST_FORWARD_AUTH_TICKET_MAX_AGE_SECONDS=30,
    GRIST_FORWARD_AUTH_LOGIN_PATH="/auth/login",
)
class WorkHubViewTests(TestCase):
    """Work Hub HTTP 인증과 최소 응답 계약을 검증합니다."""

    def test_webhook_rejects_missing_secret(self) -> None:
        """Webhook Bearer secret이 없으면 요청을 처리하지 않습니다."""

        response = self.client.post(
            "/api/v1/work-hub/webhooks/grist?doc_id=doc-a&table_id=WorkLog",
            data=[{"id": 1}],
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(GristWebhookReceipt.objects.count(), 0)

    @patch("api.work_hub.views.enqueue_grist_webhook")
    def test_disabled_work_hub_rejects_webhook_before_processing(
        self,
        enqueue_webhook,
    ) -> None:
        """기능을 끄면 유효한 전용 token의 Webhook도 처리하지 않습니다."""

        token = build_grist_webhook_token(doc_id="doc-a", table_id="WorkLog")
        with self.settings(WORK_HUB_ENABLED=False):
            response = self.client.post(
                "/api/v1/work-hub/webhooks/grist?doc_id=doc-a&table_id=WorkLog",
                data=[{"id": 1}],
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )

        self.assertEqual(response.status_code, 403)
        enqueue_webhook.assert_not_called()

    @patch("api.work_hub.views.enqueue_grist_webhook")
    def test_webhook_accepts_only_target_scoped_token(self, enqueue_webhook) -> None:
        """한 document의 Webhook token은 다른 document 요청에 재사용할 수 없습니다."""

        enqueue_webhook.return_value = {
            "event_id": "grist:test",
            "duplicate": False,
            "status": GristWebhookReceipt.Status.RECEIVED,
        }
        token = build_grist_webhook_token(doc_id="doc-a", table_id="WorkLog")

        accepted = self.client.post(
            "/api/v1/work-hub/webhooks/grist?doc_id=doc-a&table_id=WorkLog",
            data=[{"id": 1}],
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        rejected_other_document = self.client.post(
            "/api/v1/work-hub/webhooks/grist?doc_id=doc-b&table_id=WorkLog",
            data=[{"id": 1}],
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        rejected_master_secret = self.client.post(
            "/api/v1/work-hub/webhooks/grist?doc_id=doc-a&table_id=WorkLog",
            data=[{"id": 1}],
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-webhook-secret",
        )

        self.assertEqual(accepted.status_code, 202)
        self.assertEqual(rejected_other_document.status_code, 403)
        self.assertEqual(rejected_master_secret.status_code, 403)
        enqueue_webhook.assert_called_once()

    @patch("api.work_hub.views.enqueue_grist_webhook")
    def test_webhook_rejects_invalid_row_before_enqueue(self, enqueue_webhook) -> None:
        """row ID가 없는 payload는 worker queue에 저장하지 않습니다."""

        token = build_grist_webhook_token(doc_id="doc-a", table_id="WorkLog")

        response = self.client.post(
            "/api/v1/work-hub/webhooks/grist?doc_id=doc-a&table_id=WorkLog",
            data=[{"follow_up_required": True}],
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 400)
        enqueue_webhook.assert_not_called()

    def test_work_hub_access_scope_exists(self) -> None:
        """data migration이 affiliation 기반 앱 scope를 생성합니다."""

        scope = account_selectors.get_access_scope_by_key(scope_key="work-hub")

        self.assertIsNotNone(scope)
        self.assertEqual(scope.scope_type, "app")
        self.assertEqual(scope.data_scope_type, "affiliation")

    def test_context_endpoint_returns_mapping_without_credentials(self) -> None:
        """context 응답에는 launch 정보만 있고 Grist key와 secret은 없습니다."""

        admin = get_user_model().objects.create_superuser(
            sabun="WHVIEWADMIN",
            password="password",
            knox_id="work-hub-admin",
        )
        account_services.set_current_affiliation_for_user(
            user=admin,
            department="ETCH",
            line="L1",
            user_sdwt_prod="SDWT-VIEW",
        )
        affiliation = account_selectors.get_active_affiliation_by_user_sdwt_prod(
            user_sdwt_prod="SDWT-VIEW",
        )
        GristDocumentScope.objects.create(
            affiliation=affiliation,
            workspace_id=1,
            doc_id="doc-view",
            launch_url="http://localhost:8100/o/work-hub/doc/doc-view/p/3",
        )
        self.client.force_login(admin)

        response = self.client.get("/api/v1/work-hub/context")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "single")
        self.assertNotIn("key", str(response.json()).lower())
        self.assertNotIn("secret", str(response.json()).lower())

    def test_grist_forward_auth_returns_verified_portal_account_email(self) -> None:
        """승인된 ticket은 원래 문서 경로를 유지하고 신뢰할 email로 교환됩니다."""

        admin = get_user_model().objects.create_superuser(
            sabun="WHCONNECTADMIN",
            password="password",
            email="Portal.Admin@Example.Invalid",
            username="Portal Admin",
        )
        self.client.force_login(admin)

        response = self.client.get(
            "/auth/grist/login",
            {
                "return_url": "http://grist.example.invalid/auth/login",
                "next": "/o/work-hub/doc/doc-view/p/3",
            },
        )

        self.assertEqual(response.status_code, 302)
        redirect_query = parse_qs(urlparse(response["Location"]).query)
        self.assertEqual(len(redirect_query["ticket"]), 1)
        self.assertEqual(
            redirect_query["next"],
            ["/o/work-hub/doc/doc-view/p/3"],
        )

        verify_response = self.client.get(
            "/auth/grist/verify",
            HTTP_X_GRIST_ORIGINAL_URI=(
                f"/auth/login?{urlparse(response['Location']).query}"
            ),
        )

        self.assertEqual(verify_response.status_code, 204)
        self.assertEqual(
            verify_response["X-Portal-User-Email"],
            "portal.admin@example.invalid",
        )
        self.assertEqual(verify_response["Cache-Control"], "no-store")

    def test_grist_forward_auth_rejects_tampered_next_path(self) -> None:
        """발급 뒤 바뀐 문서 경로는 유효한 ticket과 함께 와도 거부합니다."""

        admin = get_user_model().objects.create_superuser(
            sabun="WHNEXTADMIN",
            password="password",
            email="next.admin@example.invalid",
        )
        self.client.force_login(admin)
        issued = self.client.get(
            "/auth/grist/login",
            {
                "return_url": "http://grist.example.invalid/auth/login",
                "next": "/o/work-hub/doc/doc-a",
            },
        )
        ticket = parse_qs(urlparse(issued["Location"]).query)["ticket"][0]

        response = self.client.get(
            "/auth/grist/verify",
            HTTP_X_GRIST_ORIGINAL_URI=(
                f"/auth/login?ticket={ticket}&next=/o/work-hub/doc/doc-b"
            ),
        )

        self.assertEqual(response.status_code, 401)

    def test_grist_forward_auth_rejects_external_next_url(self) -> None:
        """외부 origin을 가리키는 next URL은 ticket을 발급하지 않습니다."""

        admin = get_user_model().objects.create_superuser(
            sabun="WHNEXTURLADMIN",
            password="password",
            email="next-url.admin@example.invalid",
        )
        self.client.force_login(admin)

        response = self.client.get(
            "/auth/grist/login",
            {
                "return_url": "http://grist.example.invalid/auth/login",
                "next": "https://attacker.example.invalid/collect",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_grist_forward_auth_rejects_invalid_ticket(self) -> None:
        """Portal이 서명하지 않은 ticket은 신뢰할 email로 교환하지 않습니다."""

        response = self.client.get(
            "/auth/grist/verify",
            HTTP_X_GRIST_ORIGINAL_URI="/auth/login?ticket=invalid",
        )

        self.assertEqual(response.status_code, 401)

    def test_grist_forward_auth_feature_flag_blocks_login_and_existing_ticket(
        self,
    ) -> None:
        """기능 플래그가 꺼지면 새 login과 이미 발급한 ticket을 모두 차단합니다."""

        admin = get_user_model().objects.create_superuser(
            sabun="WHFLAGADMIN",
            password="password",
            email="flag.admin@example.invalid",
        )
        self.client.force_login(admin)
        issued = self.client.get(
            "/auth/grist/login",
            {"return_url": "http://grist.example.invalid/auth/login"},
        )
        self.assertEqual(issued.status_code, 302)
        ticket = parse_qs(urlparse(issued["Location"]).query)["ticket"][0]

        with self.settings(WORK_HUB_ENABLED=False):
            login_response = self.client.get(
                "/auth/grist/login",
                {"return_url": "http://grist.example.invalid/auth/login"},
            )
            verify_response = self.client.get(
                "/auth/grist/verify",
                HTTP_X_GRIST_ORIGINAL_URI=f"/auth/login?ticket={ticket}",
            )

        self.assertEqual(login_response.status_code, 403)
        self.assertEqual(verify_response.status_code, 403)

    @patch("api.work_hub.views.auth_services.auth_login")
    def test_grist_forward_auth_starts_portal_login_for_anonymous_user(
        self,
        auth_login,
    ) -> None:
        """익명 forward-auth 요청은 기존 Portal OIDC 로그인으로 이어집니다."""

        auth_login.return_value = SimpleNamespace(
            bad_request_message="",
            authorize_url="http://localhost:9102/authorize?client_id=dummy-client",
        )

        response = self.client.get(
            "/auth/grist/login",
            {
                "return_url": "http://grist.example.invalid/auth/login",
                "next": "/o/work-hub/doc/doc-view/p/3",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            "http://localhost:9102/authorize?client_id=dummy-client",
        )
        requested_target = auth_login.call_args.kwargs["requested_target"]
        self.assertIn("/auth/grist/login", requested_target)
        requested_query = parse_qs(urlparse(requested_target).query)
        self.assertEqual(
            requested_query["return_url"],
            ["http://grist.example.invalid/auth/login"],
        )
        self.assertEqual(
            requested_query["next"],
            ["/o/work-hub/doc/doc-view/p/3"],
        )

    @override_settings(WORK_HUB_ENABLED=False)
    @patch("api.work_hub.views.auth_services.auth_login")
    def test_disabled_grist_forward_auth_does_not_start_anonymous_login(
        self,
        auth_login,
    ) -> None:
        """기능이 꺼진 익명 요청은 Portal IdP 호출 전에 거부합니다."""

        response = self.client.get(
            "/auth/grist/login",
            {"return_url": "http://grist.example.invalid/auth/login"},
        )

        self.assertEqual(response.status_code, 403)
        auth_login.assert_not_called()

    @patch("api.work_hub.views.has_grist_forward_auth_access", return_value=False)
    def test_grist_forward_auth_rejects_account_without_work_hub_access(
        self,
        _has_access,
    ) -> None:
        """Portal 로그인만 있고 Work Hub 승인이 없는 account는 Grist에 로그인하지 못합니다."""

        user = get_user_model().objects.create_user(
            sabun="WHCONNECTDENIED",
            password="password",
            email="denied@example.invalid",
        )
        self.client.force_login(user)

        response = self.client.get(
            "/auth/grist/login",
            {"return_url": "http://grist.example.invalid/auth/login"},
        )

        self.assertEqual(response.status_code, 403)

    def test_grist_forward_auth_rejects_untrusted_return_origin(self) -> None:
        """설정된 Grist origin이 아닌 로그인 return URL은 거부합니다."""

        response = self.client.get(
            "/auth/grist/login",
            {"return_url": "https://attacker.example.invalid/auth/login"},
        )

        self.assertEqual(response.status_code, 400)
