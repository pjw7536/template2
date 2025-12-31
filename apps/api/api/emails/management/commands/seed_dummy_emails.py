# =============================================================================
# 모듈 설명: 로컬 개발용 더미 이메일 생성/등록 커맨드를 제공합니다.
# - 주요 대상: seed_dummy_emails 관리 명령
# - 불변 조건: 더미 RAG 엔드포인트가 활성화되어 있어야 합니다.
# =============================================================================

"""로컬 개발용 더미 이메일을 생성하고 RAG에 등록하는 커맨드.

- 주요 대상: seed_dummy_emails 관리 명령
- 주요 엔드포인트/클래스: Command
- 가정/불변 조건: 더미 RAG 엔드포인트가 활성화되어 있음
"""
from __future__ import annotations

import os
from datetime import timedelta
from typing import Any, List

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.emails.services import register_email_to_rag
from api.emails.models import Email


def _default_recipient() -> str:
    """더미 메일 수신자 주소를 환경변수에서 읽어 반환합니다.

    입력:
    - 없음

    반환:
    - str: 수신자 이메일 주소

    부작용:
    - 없음

    오류:
    - 없음
    """

    return os.getenv("DUMMY_ADFS_EMAIL", "dummy.user@example.com")


class Command(BaseCommand):
    """로컬 개발용 더미 이메일을 생성하고 더미 RAG에 등록합니다."""

    help = "Seed deterministic dummy emails for local dev and register them to the dummy RAG."

    def handle(self, *args: Any, **options: Any) -> None:
        """더미 이메일을 생성/갱신하고 RAG 등록을 수행합니다.

        입력:
        - args/options: Django management command 인자

        반환:
        - 없음

        부작용:
        - Email 모델에 DB 쓰기
        - RAG 등록 API 호출

        오류:
        - 없음(개별 실패는 로그로 수집)
        """
        # -----------------------------------------------------------------------------
        # 1) 기본 값 및 샘플 데이터 준비
        # -----------------------------------------------------------------------------
        now = timezone.now()
        recipient = _default_recipient()
        recipients = [recipient]
        participants_search = recipient.lower()
        samples = [
            {
                "message_id": "msg-0001",
                "rag_doc_id": "email-1",
                "subject": "[샘플] 생산 라인 점검 알림",
                "sender": "alerts@example.com",
                "sender_id": "alerts",
                "recipient": recipients,
                "cc": None,
                "participants_search": participants_search,
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
                "recipient": recipients,
                "cc": None,
                "participants_search": participants_search,
                "user_sdwt_prod": "MAINT",
                "body_text": "Etch 장비 교체 작업이 예정되어 있습니다. 관련 문서를 확인해주세요.",
                "received_at": now - timedelta(hours=4),
            },
        ]

        # -----------------------------------------------------------------------------
        # 2) 결과 카운터 초기화
        # -----------------------------------------------------------------------------
        created = 0
        updated = 0
        rag_synced = 0
        rag_failures: List[str] = []

        # -----------------------------------------------------------------------------
        # 3) 샘플 업서트 및 RAG 등록
        # -----------------------------------------------------------------------------
        for sample in samples:
            defaults = {
                "subject": sample["subject"],
                "sender": sample["sender"],
                "sender_id": sample["sender_id"],
                "recipient": sample["recipient"],
                "cc": sample["cc"],
                "participants_search": sample["participants_search"],
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

        # -----------------------------------------------------------------------------
        # 4) 처리 결과 출력
        # -----------------------------------------------------------------------------
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded dummy emails - created: {created}, updated: {updated}, rag_synced: {rag_synced}"
            )
        )

        if rag_failures:
            self.stderr.write("RAG sync failed for: " + ", ".join(rag_failures))
