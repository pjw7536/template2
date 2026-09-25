"""참조테이블 CSV를 검증하고 신규 사용자·등록 소속을 일괄 생성합니다."""

import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from api.account.services import register_reference_users


class Command(BaseCommand):
    help = "참조 CSV 신규 사용자 등록 (기본 dry-run, --apply로 저장)"

    def add_arguments(self, parser):
        """컨테이너에 연결한 CSV 경로와 저장 여부를 받습니다."""

        parser.add_argument("path")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        """헤더와 행을 검증하며 실패 시 개인정보 없이 원인을 보고합니다."""

        try:
            with open(options["path"], encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source)
                required = {"epid", "sabun", "knox_id", "user_sdwt_prod"}
                allowed = required | {"username", "email", "department"}
                headers = reader.fieldnames or []
                if not required.issubset(headers) or set(headers) - allowed or len(set(headers)) != len(headers):
                    raise CommandError("CSV 헤더: epid,sabun,knox_id,user_sdwt_prod 필수; username,email,department 선택")
                records = list(reader)
                if not records or any(None in row or any(value is None for value in row.values()) for row in records):
                    raise CommandError("CSV에 행이 없거나 열 수가 맞지 않습니다.")
                result = register_reference_users(records=records, apply=options["apply"])
        except (OSError, UnicodeError, csv.Error) as error:
            raise CommandError("CSV 파일을 읽을 수 없습니다.") from error
        except ValueError as error:
            raise CommandError(str(error)) from error
        except IntegrityError as error:
            raise CommandError("사용자 식별자 충돌로 전체 등록을 취소했습니다.") from error
        mode = "등록 완료" if options["apply"] else "검증 완료 (저장하지 않음)"
        self.stdout.write(f"{mode}: 신규 {result['created']}명, 기존 {result['skipped']}명")
