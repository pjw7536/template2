# =============================================================================
# 모듈 설명: 이메일 RAG Outbox를 처리하는 관리 명령을 제공합니다.
# - 주요 클래스: Command
# - 불변 조건: 처리 로직은 서비스 계층(process_email_outbox_batch)에 위임합니다.
# =============================================================================

from __future__ import annotations

from django.core.management.base import BaseCommand

from api.emails.services import process_email_outbox_batch


class Command(BaseCommand):
    """이메일 Outbox 처리를 수행하는 관리 명령입니다."""

    help = "Process pending email outbox items for RAG operations."

    def add_arguments(self, parser) -> None:
        """명령행 인자를 추가합니다.

        입력:
            parser: argparse 파서.
        반환:
            없음.
        부작용:
            파서에 인자 정의 추가.
        오류:
            없음.
        """

        parser.add_argument("--limit", type=int, default=100, help="Max outbox items to process in one run.")

    def handle(self, *args, **options) -> None:
        """Outbox 처리 명령을 실행합니다.

        입력:
            options: argparse 옵션 dict.
        반환:
            없음.
        부작용:
            Outbox 처리 및 콘솔 출력.
        오류:
            서비스 오류는 예외로 전파될 수 있음.
        """

        # -----------------------------------------------------------------------------
        # 1) 옵션 파싱
        # -----------------------------------------------------------------------------
        limit = int(options.get("limit") or 100)
        result = process_email_outbox_batch(limit=limit)

        # -----------------------------------------------------------------------------
        # 2) 결과 출력
        # -----------------------------------------------------------------------------
        self.stdout.write(
            self.style.SUCCESS(
                f"Outbox processed={result['processed']} succeeded={result['succeeded']} failed={result['failed']}"
            )
        )
