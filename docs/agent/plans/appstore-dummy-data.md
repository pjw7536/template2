# ExecPlan: Appstore 개발용 더미 데이터

## 목표
- 로컬 개발 환경에 Appstore 순서 관리 화면을 시험할 수 있는 앱 더미 데이터를 제공한다.
- 동일 prefix로 재실행해도 중복되지 않고 `--reset`으로 seed 데이터만 재생성할 수 있게 한다.
- dev dummy superuser가 Appstore admin 권한으로 순서를 변경할 수 있게 한다.

## 현재 상태
- `seed_dev_data`가 account, emails, drone 더미 데이터를 통합 적재한다.
- Appstore 전용 seed service와 management command는 없다.
- dev dummy 사용자는 superuser이므로 Appstore admin 판정을 통과한다.

## 범위
- Appstore selector/service/facade와 전용 management command를 추가한다.
- 통합 `seed_dev_data`에 Appstore seed를 연결한다.
- Appstore 및 management command 테스트와 운영 문서 색인을 갱신한다.
- production 데이터나 기존 비-seed Appstore 앱은 변경하지 않는다.

## 설계
- seed 앱 이름은 `[<PREFIX>] ` marker로 식별한다.
- 8개 카테고리 샘플을 고정된 순서로 생성한다.
- 신규 항목은 `create_app`, 기존 항목은 `update_app`, reset 삭제는 `delete_app`을 사용해 순서 잠금 계약을 지킨다.
- `seed_appstore_dummy_data` command와 통합 `seed_dev_data` 모두 `ENVIRONMENT=development`에서만 실행한다.
- 소유자는 `ensure_dev_dummy_superuser()`가 보장한 dev dummy 사용자로 지정한다.

## 실행 단계
- [x] seed selector/service/facade 추가
- [x] Appstore 전용 management command 추가
- [x] 통합 dev seed 연결
- [x] 서비스/command 테스트 추가
- [x] 운영 문서 갱신
- [x] migration, seed smoke test, 테스트와 audit 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py seed_appstore_dummy_data --reset --prefix DEV`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.appstore api.management`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:docs`

## 위험과 대응
- 위험: reset이 실제 앱을 삭제할 수 있다.
- 대응: 정확한 `[PREFIX] ` 이름 marker를 가진 앱만 삭제한다.
- 위험: seed 재실행 시 순서가 계속 추가되거나 중복될 수 있다.
- 대응: marker 이름으로 기존 행을 조회해 update하고, 새 샘플만 마지막에 생성한다.

## 진행 기록
- 2026-08-08: 기존 `seed_dev_data`와 dev dummy superuser 계약을 재사용하기로 결정했다.
- 2026-08-08: `[DEV]` 앱 8개를 개발 DB에 적재하고 재실행 시 8개 update, 중복 0개를 확인했다.
- 2026-08-08: appstore/management 40개 테스트, migration check, backend boundary와 docs audit 통과를 확인했다.
