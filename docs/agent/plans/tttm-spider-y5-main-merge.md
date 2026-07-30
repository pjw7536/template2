# ExecPlan: TTTM Spider y5 브랜치 main 병합

## 목표
- 최신 `origin/y5`의 TTTM Spider backend/frontend 변경을 `main`에 병합한다.
- 병합 결과가 Django/React feature boundary와 데이터 mount 규칙을 지키는지 검증한다.
- TTTM Spider API를 `app:tttm-spider` 권한으로 보호하고 병합 후 정책 위반을 보정한다.
- 요청에 포함되지 않은 원격 push는 수행하지 않는다.

## 현재 상태
- 현재 브랜치는 `main`이고 병합 전 작업트리는 깨끗하다.
- 최신 `origin/y5` 커밋은 `f0b7a1a8`이며 `main`과 13/1 커밋으로 갈라져 있다.
- `main...origin/y5` 변경은 35개 파일, 3,851 insertions, 26 deletions다.
- 변경 범위는 신규 `api.tttm_spider` 앱, 전역 API route/settings, TTTM Spider React feature다.
- DB model은 추가되지 않으며 parquet 기반 파일 데이터를 읽는다.

## 범위
- 수정할 영역
  - `origin/y5` 병합 결과
  - 충돌 해결 또는 병합 변경으로 직접 발생한 좁은 검증 오류
  - TTTM Spider access policy와 auth 회귀 테스트
  - TTTM Spider backend 모듈/테스트/참조 데이터 배치
  - dev/oidc/prod Compose, common API env, 설정 문서의 TTTM mount 계약
  - 이 병합 작업을 추적하는 ExecPlan 문서
- 수정하지 않을 영역
  - 원격 `main` push
  - TTTM Spider 외 도메인 리팩터링
  - 사용자 확인이 필요한 API/business rule 변경

## 설계
- source는 최신 `origin/y5`, target은 현재 `main`으로 고정한다.
- TTTM Spider API는 `/api/v1/tttm_spider/`에 등록된 읽기 전용 파일 데이터 API다.
- frontend는 기존 iframe page를 feature-local React Query 기반 화면으로 대체한다.
- concrete DB model이 없으므로 migration은 예상하지 않는다.
- `/data/tttm_spider` 아래 `data`, `result`, `reference` 디렉터리를 단일 read-only mount로 제공한다.
- TTTM Spider API는 기존 system app scope인 `tttm-spider` 승인을 요구한다.
- 채점/카탈로그/개발용 mock 로직은 허용된 `services/` 아래로 이동하고 공개 facade는 유지한다.
- 독립 self-test는 Django test discovery가 실행하는 `test_scoring.py`로 전환한다.

## 실행 단계
- [x] 현재 브랜치와 작업트리 상태를 확인한다.
- [x] 최신 `origin/y5`를 fetch하고 변경 범위를 분류한다.
- [x] `origin/y5`를 `main`에 병합하고 충돌을 해결한다.
- [x] 병합 결과의 route, import, public facade, backend 책임 경계를 점검한다.
- [x] backend/frontend 검증과 migration 누락 검사를 실행한다.
- [x] 최종 상태와 남은 위험을 기록한다.
- [x] `app:tttm-spider` API 접근 정책과 회귀 테스트를 추가한다.
- [x] 비표준 backend 모듈과 self-test를 허용 구조로 이동한다.
- [x] 참조 TXT와 `/data/tttm_spider` mount 계약을 동기화한다.
- [x] 보정 후 전체 관련 검증을 다시 실행한다.

## 검증
- 통과: `git diff --check HEAD^1..HEAD`
- 통과: `git diff --check`
- 통과: `npm run agent:audit:api-boundary`
- 통과: `scripts/agent/check_frontend_boundaries.sh`
- 기존 범위 후보로 실패: `scripts/agent/check_ui_consistency.sh`
  - 병합분이 아닌 `account`, `l3-spider` 기존 inline style/raw color 후보
- 통과: `cd apps/web && npm run lint`
- 통과: `cd apps/web && npm run build`
- 통과: `bash scripts/agent/check_docs_inventory.sh`
- 통과: `bash scripts/agent/check_compose_configs.sh`
- 통과: `docker compose -f docker-compose.dev.yml exec -T api python manage.py check`
- 통과: `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- 통과: Account 전체, TTTM 전체, auth policy 회귀 테스트 (235 tests)
- 통과: dev one-off API 컨테이너의 read-only reference mount 확인
  - sensor map 7개, OES range 31개 로드
- 통과: recovery dev API의 `/api/v1/health/` 응답과 live reference mount 확인
- 별도 기존 문제: 표준 API 재생성 시 미적용 `account` migration이 존재하지 않는
  `uniq_acc_aff_usr_sdw_prd` constraint를 삭제하려 해 startup이 중단된다.
  - `docs/agent/plans/account-migration-state-recovery.md` 절차로 복구 완료했다.

## 위험과 대응
- 위험: 신규 backend app에 허용되지 않은 root-level 모듈 또는 데이터 파일이 포함될 수 있다.
- 대응: backend boundary audit 결과를 확인하고, 좁고 deterministic한 위치 보정만 수행한다.
- 위험: `/data/tttm_spider` 파일 데이터가 Compose에 mount되지 않아 로컬/운영 실행 시 빈 데이터가 될 수 있다.
- 대응: dev/oidc/prod compose, common env, 설정 문서를 대조하고 누락 여부를 보고한다.
- 위험: 기존 iframe proxy 설정과 신규 native 화면 설정이 동시에 남아 운영 계약이 불명확해질 수 있다.
- 대응: 현재 사용처를 추적하고 병합 범위를 넘어서는 cleanup은 별도 위험으로 보고한다.

## 진행 기록
- 2026-07-30: 최신 `origin/y5`를 fetch하고 TTTM Spider backend/frontend 35개 파일 변경을 확인했다.
- 2026-07-30: DB migration은 없고 `/data/tttm_spider` 읽기 계약과 backend app 구조가 주요 검증 대상임을 확인했다.
- 2026-07-30: `origin/y5`를 충돌 없이 병합해 merge commit `18a169b8`을 생성했다.
- 2026-07-30: Django check, migration check, TTTM 테스트 4개, frontend boundary, lint가 통과했다.
- 2026-07-30: backend boundary audit에서 access classification 누락과 비표준 앱 파일 5개를 확인했다.
- 2026-07-30: `/data/tttm_spider` 설정은 추가됐지만 dev/oidc/prod compose, common env, 설정 문서에 mount 계약이 동기화되지 않았음을 확인했다.
- 2026-07-30: `tttm_spider` API를 `app:tttm-spider` scope로 보호하고 auth policy 회귀 테스트를 추가했다.
- 2026-07-30: catalog/scoring/mock 로직을 `services/`로 이동하고 self-test를 Django test discovery 대상인 `test_scoring.py`로 전환했다.
- 2026-07-30: 참조 TXT를 `/data/tttm_spider/reference` host 데이터로 이동하고 dev/oidc/prod read-only mount, common env, 설정 문서를 동기화했다.
- 2026-07-30: backend boundary, Compose, Django check, migration check, 관련 테스트 11개, 실제 reference mount 로드 검증이 모두 통과했다.
- 2026-07-30: dev API에 새 mount를 적용하는 과정에서 기존 account migration/DB constraint 불일치로 표준 startup이 실패했다. DB 상태는 수정하지 않고 migration을 건너뛴 `tailwind-api-recovery` 컨테이너로 개발 API와 8000 포트를 복구했다.
- 2026-07-30: account migration ledger와 schema/data를 안전하게 일치시킨 뒤 recovery 컨테이너를 제거하고 표준 Compose API를 정상 복구했다.
- 2026-07-30: 커밋 전 최신 `origin/y5=f0b7a1a8` 포함 여부를 확인하고 backend/Compose/migration/runtime/frontend/docs 검증을 다시 통과했다.
- 2026-07-30: 문서 inventory가 찾은 TTTM API endpoint 누락 10개와 frontend route/env 색인을 `docs/inventory.md`에 보완했다.
