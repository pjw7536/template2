"""소속별 Grist workspace/document/table ID를 등록하는 명령입니다."""

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from api.work_hub.services import build_grist_webhook_token, configure_document_scope


class Command(BaseCommand):
    """운영자가 Grist UI에서 확인한 식별자를 Portal mapping으로 저장합니다."""

    help = "소속별 Grist document/table mapping을 생성하거나 갱신합니다."

    def add_arguments(self, parser) -> None:
        """필수 Grist 식별자와 launch URL 인자를 등록합니다."""

        parser.add_argument("--user-sdwt-prod", required=True)
        parser.add_argument("--workspace-id", type=int, required=True)
        parser.add_argument("--doc-id", required=True)
        parser.add_argument("--equipment-table-id", default="Equipment")
        parser.add_argument("--worklog-table-id", default="WorkLog")
        parser.add_argument("--task-table-id", default="Task")
        parser.add_argument("--launch-url", required=True)
        parser.add_argument("--template-revision", default="grist-work-hub-v1")
        parser.add_argument("--show-webhook-authorization", action="store_true")

    def handle(self, *args, **options) -> None:
        """검증된 mapping을 저장하고 생성/갱신 결과를 출력합니다."""

        webhook_token = ""
        if options["show_webhook_authorization"]:
            webhook_token = build_grist_webhook_token(
                doc_id=options["doc_id"],
                table_id=options["worklog_table_id"],
            )
            if not webhook_token:
                raise CommandError("GRIST_WEBHOOK_SECRET 설정이 필요합니다.")

        try:
            mapping, created = configure_document_scope(
                user_sdwt_prod=options["user_sdwt_prod"],
                workspace_id=options["workspace_id"],
                doc_id=options["doc_id"],
                equipment_table_id=options["equipment_table_id"],
                worklog_table_id=options["worklog_table_id"],
                task_table_id=options["task_table_id"],
                launch_url=options["launch_url"],
                template_revision=options["template_revision"],
            )
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        action = "생성" if created else "갱신"
        self.stdout.write(self.style.SUCCESS(f"Grist mapping {action}: doc={mapping.doc_id}"))
        if webhook_token:
            self.stdout.write(f"Webhook Authorization: Bearer {webhook_token}")
