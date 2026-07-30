"""Data Movement loader management command의 공통 실행 흐름을 제공합니다."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

OutcomeField = tuple[str, str, str | None]


class DataMovementLoadCommand(BaseCommand):
    """테이블 loader 호출과 표준 결과 출력을 수행하는 command 기반 클래스."""

    service_module: Any = None
    loader_name = ""
    table_name = ""
    outcome_fields: tuple[OutcomeField, ...] = (("rows", "row_count", None),)

    def add_arguments(self, parser: Any) -> None:
        """모든 파일 loader가 공유하는 command 옵션을 등록합니다."""

        parser.add_argument(
            "--data-dir",
            dest="data_dir",
            help="incoming/processing을 포함할 테이블 root",
        )
        parser.add_argument(
            "--limit",
            dest="limit",
            type=int,
            help="처리할 최대 파일 수",
        )
        parser.add_argument(
            "--dry-run",
            dest="dry_run",
            action="store_true",
            help="DB 반영 없이 파싱만 수행",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """테이블 loader를 실행하고 파일별 결과와 요약을 출력합니다."""

        loader = getattr(self.service_module, self.loader_name)
        data_dir = Path(options["data_dir"]) if options.get("data_dir") else None
        summary = loader(
            data_dir=data_dir,
            dry_run=options["dry_run"],
            limit=options.get("limit"),
        )

        if summary.processed_count == 0:
            self.stdout.write("처리할 파일 없음")
            return

        for outcome in summary.outcomes:
            self.stdout.write(self._format_outcome(outcome))

        self.stdout.write(
            f"summary: processed={summary.processed_count}, "
            f"success={summary.success_count}, failed={summary.failure_count}"
        )
        if summary.failure_count:
            raise CommandError(
                f"{self.table_name} 적재 실패 파일 수: {summary.failure_count}"
            )

    def _format_outcome(self, outcome: Any) -> str:
        """테이블별 부가 필드를 포함한 기존 outcome 출력 형식을 생성합니다."""

        fields = []
        for label, attribute, empty_value in self.outcome_fields:
            value = getattr(outcome, attribute)
            if empty_value is not None and not value:
                value = empty_value
            fields.append(f"{label}={value}")

        message = f"{outcome.status}: {outcome.file_name}, {', '.join(fields)}"
        if outcome.error_message:
            return f"{message}, error={outcome.error_message}"
        return message


__all__ = ["DataMovementLoadCommand"]
