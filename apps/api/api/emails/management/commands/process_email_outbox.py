from __future__ import annotations

from django.core.management.base import BaseCommand

from api.emails.services import process_email_outbox_batch


class Command(BaseCommand):
    help = "Process pending email outbox items for RAG operations and reclassification."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--limit", type=int, default=100, help="Max outbox items to process in one run.")

    def handle(self, *args, **options) -> None:
        limit = int(options.get("limit") or 100)
        result = process_email_outbox_batch(limit=limit)
        self.stdout.write(
            self.style.SUCCESS(
                f"Outbox processed={result['processed']} succeeded={result['succeeded']} failed={result['failed']}"
            )
        )
