# ExecPlan: Work Hub 접근 권한 정합성 보강

## 목표
- Grist ACL과 launcher가 `work-hub` 앱별 소속 데이터 범위를 동일하게 따르도록 한다.
- Grist 공개 계정, 만료·회수 grant, 비활성 소속의 잔존 ACL을 자동·수동으로 회수한다.

## 현재 상태
- Work Hub ACL은 앱 접근 허용 여부만 확인하고 앱별 소속 grant를 확인하지 않는다.
- Grist 공개용 특수 계정이 자동 회수 보호 대상에 포함되어 있다.
- `UserScopeAffiliationGrant` 변경 signal과 만료 처리 경로가 없다.
- `sync_grist_access`가 활성 소속만 대상으로 삼는다.

## 범위
- `api.account`의 scope-aware 역할 판정, grant 만료 서비스와 읽기 selector
- `api.work_hub`의 context, ACL, account signal, worker와 수동 동기화 명령
- 관련 backend 회귀 테스트와 Work Hub 운영 문서
- DB schema, frontend, Grist table 계약은 변경하지 않는다.

## 설계
- 소속별 Grist 역할 후보에 `can_access_scope_affiliation` 판정을 추가한다.
- launcher는 전역 역할과 앱별 접근 가능 소속의 교집합만 노출한다.
- `GRIST_ADMIN_EMAIL`만 회수 예외로 유지한다.
- grant 저장·삭제는 해당 소속 Outbox를 적재한다.
- worker는 활성 상태로 남은 만료 grant를 비활성화하고 기존 signal로 ACL 회수를 요청한다.
- 수동 ACL reconciliation은 mapping 활성 여부만 보고, 소속 비활성 상태는 desired state에서 빈 ACL로 처리한다.

## 실행 단계
- [x] scope-aware ACL과 launcher 구현
- [x] 공개용 Grist 계정 회수 구현
- [x] grant signal과 만료 비활성화 구현
- [x] 비활성 소속 수동 reconciliation 구현
- [x] 회귀 테스트와 문서 갱신
- [x] Docker 테스트, migration check, backend boundary audit 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.work_hub api.account`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm run agent:audit:api-boundary`
- `git diff --check`

## 위험과 대응
- 위험: scope 판정 추가로 ACL 계산 query가 증가할 수 있다.
- 대응: 기존 사용자 후보만 판정하고, correctness를 우선한 뒤 회귀 테스트로 결과 집합을 고정한다.
- 위험: 만료 검사마다 전체 ACL Outbox가 늘어날 수 있다.
- 대응: 만료 grant 자체를 한 번 비활성화해 이후 검사 대상에서 제외한다.

## 진행 기록
- 2026-08-10: 코드리뷰에서 확인한 네 권한 회수 누락을 하나의 정합성 변경으로 묶고 구현을 시작했다.
- 2026-08-10: Work Hub/account 테스트 259건, Work Hub 재검증 31건, migration check, backend boundary audit, docs audit와 diff check를 통과했다.
