from __future__ import annotations

import os
from datetime import timedelta
from typing import Any, List

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.emails.services import register_email_to_rag
from api.emails.models import Email


def _default_recipient() -> str:
    """더미 메일 수신자 주소를 환경변수에서 읽어 기본값을 반환합니다."""

    return os.getenv("DUMMY_ADFS_EMAIL", "dummy.user@example.com")


class Command(BaseCommand):
    """로컬 개발용 더미 이메일을 생성하고 더미 RAG에 등록하는 커맨드입니다."""

    help = "Seed deterministic dummy emails for local dev and register them to the dummy RAG."

    def handle(self, *args: Any, **options: Any) -> None:
        now = timezone.now()
        recipient = _default_recipient()
        samples = [
            {
                "message_id": "msg-0001",
                "rag_doc_id": "email-1",
                "subject": "[샘플] 생산 라인 점검 알림",
                "sender": "alerts@example.com",
                "sender_id": "alerts",
                "recipient": recipient,
                "user_sdwt_prod": "FAB-OPS",
                "body_text": "주간 생산 라인 점검 예정입니다. 안전 수칙을 확인해주세요.",
                "received_at": now,
            },
            {
                "message_id": "msg-0002",
                "rag_doc_id": "email-2",
                "subject": "[샘플] 장비 교체 일정 안내",
                "sender": "maintenance@example.com",
                "sender_id": "maintenance",
                "recipient": recipient,
                "user_sdwt_prod": "MAINT",
                "body_text": "Etch 장비 교체 작업이 예정되어 있습니다. 관련 문서를 확인해주세요.",
                "received_at": now - timedelta(hours=4),
            },
        ]

        created = 0
        updated = 0
        rag_synced = 0
        rag_failures: List[str] = []

        for sample in samples:
            defaults = {
                "subject": sample["subject"],
                "sender": sample["sender"],
                "sender_id": sample["sender_id"],
                "recipient": sample["recipient"],
                "user_sdwt_prod": sample["user_sdwt_prod"],
                "body_text": sample["body_text"],
                "received_at": sample["received_at"],
                "rag_doc_id": sample["rag_doc_id"],
            }

            email_obj, is_created = Email.objects.update_or_create(
                message_id=sample["message_id"],
                defaults=defaults,
            )
            created += int(is_created)
            updated += int(not is_created)

            try:
                register_email_to_rag(email_obj)
                rag_synced += 1
            except Exception as exc:
                rag_failures.append(f"{email_obj.message_id}: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded dummy emails - created: {created}, updated: {updated}, rag_synced: {rag_synced}"
            )
        )

        if rag_failures:
            self.stderr.write("RAG sync failed for: " + ", ".join(rag_failures))
