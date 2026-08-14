"""Portal 소속 사용자·역할을 Grist document ACL과 동기화합니다."""

from django.core.management.base import BaseCommand, CommandError

from api.work_hub.selectors import (
    get_access_reconciliation_document_scope_by_user_sdwt_prod,
    list_access_reconciliation_document_scopes,
)
from api.work_hub.services import sync_document_access_scope


class Command(BaseCommand):
    """한 소속 또는 모든 활성 mapping의 역할 ACL을 동기화합니다."""

    help = "Portal 소속 사용자·역할을 Grist Viewer/Editor/Owner ACL과 동기화합니다."

    def add_arguments(self, parser) -> None:
        """대상 소속과 dry-run 옵션을 등록합니다."""

        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument("--user-sdwt-prod")
        target.add_argument("--all", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options) -> None:
        """대상 mapping별 ACL 변경 통계를 출력합니다."""

        if options["all"]:
            scopes = list(list_access_reconciliation_document_scopes())
        else:
            scope = get_access_reconciliation_document_scope_by_user_sdwt_prod(
                user_sdwt_prod=options["user_sdwt_prod"],
            )
            scopes = [scope] if scope else []
        if not scopes:
            raise CommandError("동기화할 Grist mapping이 없습니다.")

        for scope in scopes:
            result = sync_document_access_scope(
                document_scope=scope,
                dry_run=options["dry_run"],
            )
            mode = "DRY-RUN" if options["dry_run"] else "APPLIED"
            self.stdout.write(
                f"{mode} {scope.affiliation.user_sdwt_prod}: "
                f"added={result['added']} updated={result['updated']} "
                f"removed={result['removed']} unchanged={result['unchanged']}"
            )
