"""로컬 개발용 Grist 업무일지 demo를 준비하는 관리 명령입니다."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from api.work_hub.services import GristDemoError, seed_grist_demo


class Command(BaseCommand):
    """Grist demo schema·record·Webhook과 Portal mapping을 한 번에 보장합니다."""

    help = "로컬 개발용 Grist Work Hub demo 데이터를 멱등하게 생성합니다."

    def add_arguments(self, parser) -> None:
        """환경 기본 소속을 개별 실행 시 덮어쓸 수 있게 등록합니다."""

        parser.add_argument(
            "--user-sdwt-prod",
            default=str(getattr(settings, "GRIST_DEV_USER_SDWT_PROD", "DEV_ALPHA")),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """demo 리소스를 생성하고 브라우저 접속에 필요한 식별자를 출력합니다."""

        try:
            result = seed_grist_demo(
                user_sdwt_prod=str(options["user_sdwt_prod"]).strip(),
            )
        except (GristDemoError, ValidationError) as exc:
            raise CommandError(str(exc)) from exc

        mapping_action = "생성" if result.mapping_created else "갱신"
        self.stdout.write(
            self.style.SUCCESS(
                "Grist demo 준비 완료: "
                f"workspace={result.workspace_id} "
                f"doc={result.doc_id} "
                f"tables={result.equipment_table_id}/{result.worklog_table_id}/{result.task_table_id} "
                f"rows={result.equipment_rows}/{result.worklog_rows}/{result.task_rows} "
                f"mapping={mapping_action}"
            )
        )
