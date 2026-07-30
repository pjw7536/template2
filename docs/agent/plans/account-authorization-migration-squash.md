# ExecPlan: Account 권한 migration 통합

## 목표
- 아직 적용되지 않은 Account `0006~0009` migration을 단일 `0006`으로 통합한다.
- 기존 데이터 검증·보정과 최종 스키마 제약의 의미와 실행 순서를 보존한다.

## 현재 상태
- 공유 기준 migration은 `0005_fixed_access_roles`이다.
- `0006_affiliation_access_integrity`, `0007_app_affiliation_data_scope`,
  `0008_affiliation_identifier_format`, `0009_authorization_review_remediation`은
  아직 적용되지 않았다.
- Account 테스트와 운영 문서 일부가 개별 migration 이름을 참조한다.

## 범위
- 수정할 영역:
  - `apps/api/api/account/migrations`
  - Account migration 회귀 테스트
  - 개별 migration 이름을 참조하는 운영·설계 문서
- 수정하지 않을 영역:
  - 현재 Django model과 런타임 권한 정책
  - API와 frontend 계약
  - `0005` 이하 migration 이력

## 설계
- 단일 `0006_account_authorization_system`이 `0005_fixed_access_roles`에 의존한다.
- 소속 데이터 검증 후 역할·소속 식별자 제약을 추가한다.
- 앱별 소속 범위 필드·모델·제약을 만든 뒤 기존 grant를 변환한다.
- 중복 `PENDING` 소속 요청을 최신 한 건만 남기고 정리한 뒤 조건부 unique
  constraint를 추가한다.
- 감사 action 필드는 중간 상태를 거치지 않고 최종 choices로 한 번만 변경한다.
- public API/facade와 env 계약은 변경하지 않는다.

## 실행 단계
- [x] 네 migration의 operation과 데이터 migration 함수를 단일 `0006`으로 통합한다.
- [x] 기존 `0006~0009` 파일을 제거한다.
- [x] migration 테스트와 문서의 migration 이름을 갱신한다.
- [x] migration graph와 미생성 migration 여부를 확인한다.
- [x] Account 테스트와 정적 경계 검사를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py showmigrations account`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account --noinput`
- `npm run agent:audit:api-boundary`
- `git diff --check`

## 위험과 대응
- 위험: 데이터 migration 순서를 바꾸면 새 필드나 제약이 없는 상태에서 데이터 보정이 실행될 수 있다.
- 대응: 기존 실행 순서인 무결성 검증 → 스키마 생성 → 앱별 grant 변환 → 대기 요청 정리 → 최종 제약 추가를 유지한다.
- 위험: 테스트가 삭제된 중간 migration 노드를 참조할 수 있다.
- 대응: migration 테스트를 `0005`에서 통합 `0006`으로 이동하도록 갱신하고 전체 Account 테스트를 실행한다.
- 위험: 이미 적용된 DB가 있다면 migration ledger와 파일 그래프가 어긋난다.
- 대응: 사용자가 확인한 “미적용” 전제에서만 통합하고 실제 적용 전 `showmigrations account`로 ledger를 확인한다.

## 진행 기록
- 2026-07-30: 사용자 확인에 따라 `0006~0009`가 미적용임을 전제로 통합을 시작했다.
- 2026-07-30: 개발 DB ledger가 `0005`까지 적용되고 통합 `0006`만 미적용인 상태임을 확인했다.
- 2026-07-30: 통합 migration 적용·역적용을 포함한 전용 테스트 2개와 Account 전체 210개 테스트를 통과했다.
- 2026-07-30: migration graph/plan, 미생성 migration, Django system check, backend 경계, 문서 inventory, diff 검사를 통과했다.
- 2026-07-30: `pre-migration` 무결성 검사는 `0005` 이전 legacy 역할 점검용이라 현재 `0005`의 `user` 역할 60건을 오류로 보고했으며, 통합 `0006` 검증에는 사용하지 않았다.
