"""Portal 기준 Grist 접근 권한 Outbox와 Webhook 처리 명령입니다."""

from __future__ import annotations

import time

from django.conf import settings
from django.core.management.base import BaseCommand

from api.work_hub.services import (
    process_access_sync_outbox_batch,
    process_grist_webhook_batch,
    prune_completed_access_sync_outbox,
    prune_completed_webhook_receipts,
    prune_failed_webhook_receipts,
    reconcile_all_document_access_scopes,
)


class Command(BaseCommand):
    """대기 중인 Grist 접근 권한과 Webhook 작업을 처리합니다."""

    help = "Portal 기준 Grist 접근 권한 Outbox와 Webhook을 처리합니다."

    def add_arguments(self, parser) -> None:
        """처리 건수와 지속 실행 옵션을 등록합니다."""

        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--webhook-limit", type=int, default=20)
        parser.add_argument("--expire-limit", type=int, default=100)
        parser.add_argument(
            "--reconcile-interval-seconds",
            type=float,
            default=getattr(
                settings,
                "WORK_HUB_KEYCLOAK_RECONCILE_INTERVAL_SECONDS",
                300,
            ),
        )
        parser.add_argument(
            "--retention-days",
            type=int,
            default=getattr(settings, "WORK_HUB_ACCESS_OUTBOX_RETENTION_DAYS", 30),
        )
        parser.add_argument(
            "--prune-interval-seconds",
            type=float,
            default=getattr(
                settings,
                "WORK_HUB_ACCESS_OUTBOX_PRUNE_INTERVAL_SECONDS",
                3600,
            ),
        )
        parser.add_argument(
            "--webhook-retention-days",
            type=int,
            default=getattr(
                settings,
                "WORK_HUB_WEBHOOK_RECEIPT_RETENTION_DAYS",
                30,
            ),
        )
        parser.add_argument(
            "--failed-webhook-retention-days",
            type=int,
            default=getattr(
                settings,
                "WORK_HUB_FAILED_WEBHOOK_RECEIPT_RETENTION_DAYS",
                90,
            ),
        )
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--poll-seconds", type=float, default=5.0)

    def handle(self, *args, **options) -> None:
        """한 번 처리하거나 worker 형태로 반복 처리합니다."""

        limit = max(1, int(options["limit"]))
        webhook_limit = max(1, int(options["webhook_limit"]))
        expire_limit = max(1, int(options["expire_limit"]))
        retention_days = max(1, int(options["retention_days"]))
        webhook_retention_days = max(1, int(options["webhook_retention_days"]))
        failed_webhook_retention_days = max(
            1,
            int(options["failed_webhook_retention_days"]),
        )
        prune_interval_seconds = max(
            60.0,
            float(options["prune_interval_seconds"]),
        )
        poll_seconds = max(1.0, float(options["poll_seconds"]))
        next_prune_at = 0.0
        reconcile_interval_seconds = min(
            300.0,
            max(30.0, float(options["reconcile_interval_seconds"])),
        )
        next_reconcile_at = 0.0
        while True:
            work_hub_enabled = bool(getattr(settings, "WORK_HUB_ENABLED", False))
            expired = 0
            now = time.monotonic()
            pruned_outbox = 0
            pruned_webhooks = 0
            pruned_failed_webhooks = 0
            reconciled = {"processed": 0, "succeeded": 0, "failed": 0}
            webhook_result = {"processed": 0, "succeeded": 0, "failed": 0}
            if work_hub_enabled:
                webhook_result = process_grist_webhook_batch(limit=webhook_limit)
            if now >= next_prune_at:
                pruned_outbox = prune_completed_access_sync_outbox(
                    retention_days=retention_days,
                )
                pruned_webhooks = prune_completed_webhook_receipts(
                    retention_days=webhook_retention_days,
                )
                pruned_failed_webhooks = prune_failed_webhook_receipts(
                    retention_days=failed_webhook_retention_days,
                )
                next_prune_at = now + prune_interval_seconds
            if work_hub_enabled and now >= next_reconcile_at:
                reconciled = reconcile_all_document_access_scopes()
                next_reconcile_at = now + reconcile_interval_seconds
            result = {"processed": 0, "succeeded": 0, "failed": 0}
            if work_hub_enabled:
                result = process_access_sync_outbox_batch(limit=limit)
            if (
                expired
                or pruned_outbox
                or pruned_webhooks
                or pruned_failed_webhooks
                or reconciled["processed"]
                or webhook_result["processed"]
                or result["processed"]
            ):
                self.stdout.write(
                    "Grist access sync "
                    f"expired={expired} "
                    f"pruned_outbox={pruned_outbox} "
                    f"pruned_webhooks={pruned_webhooks} "
                    f"pruned_failed_webhooks={pruned_failed_webhooks} "
                    f"reconciled={reconciled['succeeded']} "
                    f"reconcile_failed={reconciled['failed']} "
                    f"webhooks={webhook_result['succeeded']} "
                    f"webhook_failed={webhook_result['failed']} "
                    f"processed={result['processed']} "
                    f"succeeded={result['succeeded']} failed={result['failed']}"
                )
            if not options["loop"]:
                return
            time.sleep(poll_seconds)
