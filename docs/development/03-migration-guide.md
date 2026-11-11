# DB migration 작성·검증

[문서 홈](../README.md) · [백엔드](02-backend.md) · [개발 작업 흐름](../getting-started/02-usage.md)

Portal API의 DB 구조를 바꿀 때 개발 PC에서 migration을 만들고 검증하는 기준입니다.
사내 서버의 적용 절차(쓰기 중지·백업·사전/사후 무결성 검사·migrate Job·서비스 재개)는
[운영 Migration 절차](../../deploy/portal/docs/01-install.md#3-migration)가 원본입니다.

## 1. 생성

migration 생성과 특정 feature 테스트는 [테스트·migration 스킬](../../.codex/skills/django-test-migration-flow/SKILL.md)을 따릅니다.
검사 이미지는 소스를 내장하므로 생성 파일을 보존하려면 스킬의 소스 마운트 명령을 사용합니다.

## 2. 로컬 검증

```bash
make k8s-rebuild APP=portal
make makemigrations-check
make test-api
```

**기대 결과:** `makemigrations-check`가 누락 migration 없이 끝나고 테스트가 통과합니다.
실패하면 소스를 수정한 뒤 검사 이미지를 다시 빌드하고 같은 순서로 검사합니다.

## 3. 배포 전 작성자 확인

서버 적용 담당자가 운영 절차를 진행할 수 있도록 PR·배포 요청에 아래 내용을 남깁니다.

| 항목 | 확인할 내용 |
| --- | --- |
| SQL·데이터 변경 | `sqlmigrate`로 본 SQL, 대량 갱신·잠금·삭제 여부, 되돌릴 수 없는 변경 |
| 실행 의존성 | 함께 중지해야 하는 worker·Airflow 작업, 이전 버전 API와의 호환 여부 |
| DB 확장 | 새 확장이 필요하면 운영 DB에서 미리 준비. 현재 필수 확장은 [`pg_trgm`](../reference/01-configuration.md#postgresql-필수-확장) |
| 권한 데이터 | Account 무결성 검사(`check_access_permission_integrity`)에 영향이 있는지 |

## 계약

- 운영 API entrypoint는 migration을 자동 실행하지 않습니다. 운영 적용은 API 시작과 분리한 migrate Job으로 수행합니다.
- 로그인 권한은 Keycloak 앱 역할·SDWT 그룹으로 관리합니다. migration으로 로그인 권한을 부여하거나 기존 사용자 권한을 일괄 변경하지 않습니다.
- 기존 DB 권한 관리 API는 `410 managed_by_keycloak`을 반환합니다. 적용 후 재로그인하면 `/api/v1/auth/me`의 `scopeAccess`·`sdwtAccess`가 Keycloak 역할·그룹과 일치해야 합니다.
