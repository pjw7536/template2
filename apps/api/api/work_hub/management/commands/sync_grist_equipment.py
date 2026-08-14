"""Observer 설비 기준정보를 Grist Equipment table과 동기화합니다."""

from django.core.management.base import BaseCommand, CommandError

from api.account import selectors as account_selectors
from api.work_hub.selectors import (
    get_document_scope_by_affiliation_id,
    list_active_document_scopes,
)
from api.work_hub.services import sync_equipment_scope


class Command(BaseCommand):
    """한 소속 또는 모든 활성 mapping의 설비를 멱등하게 동기화합니다."""

    help = "Observer 설비를 Grist Equipment table에 upsert합니다."

    def add_arguments(self, parser) -> None:
        """대상 소속과 dry-run 옵션을 등록합니다."""

        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument("--user-sdwt-prod")
        target.add_argument("--all", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options) -> None:
        """대상 mapping별 동기화 통계를 출력합니다."""

        if options["all"]:
            scopes = list(list_active_document_scopes())
        else:
            affiliation = account_selectors.get_active_affiliation_by_user_sdwt_prod(
                user_sdwt_prod=options["user_sdwt_prod"],
            )
            if affiliation is None:
                raise CommandError("활성 Affiliation을 찾을 수 없습니다.")
            scope = get_document_scope_by_affiliation_id(affiliation_id=affiliation.id)
            scopes = [scope] if scope and scope.is_active else []
        if not scopes:
            raise CommandError("동기화할 활성 Grist mapping이 없습니다.")

        for scope in scopes:
            result = sync_equipment_scope(
                document_scope=scope,
                dry_run=options["dry_run"],
            )
            mode = "DRY-RUN" if options["dry_run"] else "APPLIED"
            self.stdout.write(
                f"{mode} {scope.affiliation.user_sdwt_prod}: "
                f"created={result['created']} updated={result['updated']} "
                f"archived={result['archived']} unchanged={result['unchanged']}"
            )
