# =============================================================================
# 모듈 설명: 로컬 개발용 Appstore 더미 앱 적재 command를 제공합니다.
# - 주요 클래스: Command
# - 불변 조건: ENVIRONMENT=development에서만 실행합니다.
# =============================================================================

from __future__ import annotations

import os
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from api.account.services import ensure_dev_dummy_superuser
from api.appstore.services import seed_appstore_dummy_data


def _ensure_dev_seed_allowed() -> None:
    """Appstore seed가 development 환경에서만 실행되도록 제한합니다."""

    if (os.getenv("ENVIRONMENT") or "").strip().lower() != "development":
        raise CommandError(
            "seed_appstore_dummy_data는 로컬 dev 환경에서만 실행할 수 있습니다. "
            "ENVIRONMENT=development 설정을 확인하세요."
        )


class Command(BaseCommand):
    """Appstore 순서 관리 확인용 더미 앱을 적재합니다."""

    help = "Seed deterministic Appstore apps for local development only."

    def add_arguments(self, parser) -> None:
        """커맨드 인자를 정의합니다."""

        parser.add_argument("--prefix", type=str, default="DEV", help="더미 앱 식별 prefix. 예: DEV")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="동일 prefix의 Appstore 더미 앱을 먼저 삭제한 뒤 다시 생성합니다.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """dev dummy 사용자를 소유자로 지정해 Appstore 더미 앱을 적재합니다."""

        _ensure_dev_seed_allowed()
        prefix = str(options.get("prefix") or "").strip().upper()
        if not prefix:
            raise CommandError("--prefix must not be empty")

        owner = ensure_dev_dummy_superuser()
        if owner is None:
            raise CommandError("dev dummy 사용자를 보장하지 못했습니다. DUMMY_ADFS_* 설정을 확인하세요.")

        result = seed_appstore_dummy_data(
            prefix=prefix,
            owner=owner,
            reset=bool(options.get("reset")),
        )
        self.stdout.write(self.style.SUCCESS(f"[appstore-seed] done {result}"))
