# ExecPlan: 운영 legacy runtime 계약 정리

## 목표
- 운영 설정을 canonical DB/OIDC env key로만 해석한다.
- 효과가 없는 env key와 Drone seed의 구형 입력 별칭을 제거한다.
- 기존 운영 데이터 보호에 필요한 compatibility는 유지한다.

## 현재 상태
- Django settings가 `DJANGO_DB_*` 외에 `DB_*`, `OIDC_*` 외에 과거 ADFS/Google key를 fallback으로 읽는다.
- `DJANGO_DB_ENGINE`은 env와 문서에 있지만 settings가 사용하지 않는다.
- Drone target seed는 `user_sdwt_prod`를 canonical target/recipient 값으로 자동 해석한다.
- Spider legacy 오류·파일 구조, Assistant `legacy-unresolved`, 기존 delivery column과 Email Outbox 과거 row 보호는 운영 데이터 때문에 유지해야 한다.

## 범위
- 수정: Django settings와 개발 DB 준비 명령, API common/test env, configuration 문서, Drone seed command/service/tests, Line Dashboard 운영 문서.
- 유지: DB schema/migration, public HTTP API, Spider compatibility, Assistant provenance 보호, Line Dashboard 기존 DB column, Email Outbox 과거 action 처리.

## 설계
- DB는 `DJANGO_DB_NAME`, `DJANGO_DB_USER`, `DJANGO_DB_PASSWORD`, `DJANGO_DB_HOST`, `DJANGO_DB_PORT`만 읽는다.
- 개발 DB 준비 명령도 같은 `DJANGO_DB_*` 계약만 사용한다.
- OIDC는 `OIDC_CLIENT_ID`, `OIDC_ISSUER`, `OIDC_REDIRECT_URI`만 읽고 과거 ADFS/Google alias는 읽지 않는다.
- `DJANGO_DB_ENGINE`은 PostgreSQL 전용 설정과 중복되므로 env·문서에서 삭제한다.
- seed 입력은 `target_user_sdwt_prod`와 `recipient_user_sdwt_prod`를 명시적으로 요구하고 `user_sdwt_prod` alias를 거부한다.
- offsite dummy의 `DUMMY_ADFS_*`는 별도 mock 계약이므로 유지한다.

## 실행 단계
- [x] canonical env-only settings와 env/docs를 동기화한다.
- [x] Drone CSV/JSON/외부 seed normalization에서 구형 alias를 제거한다.
- [x] 구형 alias 거부 회귀 테스트를 추가한다.
- [x] Compose, Django tests/check, migration drift, 경계·문서 감사를 실행한다.

## 검증
- `docker compose -f docker-compose.test.yml run --rm api-test python manage.py test api.common.tests.StrictEnvironmentParserTests api.drone.test_target_admin_seed`
- `docker compose -f docker-compose.test.yml run --rm api-test python manage.py check`
- `docker compose -f docker-compose.test.yml run --rm api-test python manage.py makemigrations --check --dry-run`
- `bash scripts/agent/check_compose_configs.sh`
- `npm run agent:audit`
- legacy env와 seed alias 정적 검색, `git diff --check`

## 위험과 대응
- 위험: 운영이 과거 DB/OIDC key만 주입하면 새 배포가 기본값 또는 미설정 상태로 동작한다.
- 대응: 배포 전 canonical key 목록을 확인하고 OIDC/prod rendered env와 Django check를 release gate로 둔다.
- 위험: 외부 Drone seed 파일이 구형 `user_sdwt_prod`만 제공하면 command가 실패한다.
- 대응: 조용한 오분류 대신 명시적 오류를 반환하고 문서 예시는 canonical key만 유지한다.

## 진행 기록
- 2026-08-19: 사용자 확인에 따라 운영 데이터 보호 compatibility는 유지하고 dead env와 canonical-shadowing alias만 제거하기로 확정했다.
- 2026-08-19: 전체 Django 1,127개 테스트, 최종 변경 대상 24개 테스트, Django check, migration drift, OIDC/prod Compose config, agent audit, 정적 legacy 검색과 diff 검사를 통과했다.
