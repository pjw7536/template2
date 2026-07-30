# ExecPlan: 권한 매트릭스 수동 부여 사용자 필터

## 목표
- 권한 매트릭스에서 현재 표시 대상 scope 중 하나 이상에 수동 허용 권한이 있는 사용자만 조회할 수 있게 한다.

## 현재 상태
- `GET /api/v1/account/access/matrix`는 `search`, `department`, pagination query를 지원한다.
- 프론트엔드는 사용자 ID와 부서 필터 초안을 검색 버튼으로 적용한다.
- 수동 부여는 `UserAccess.status=allowed`로 저장된다.

## 범위
- account 권한 매트릭스 API에 `manualGrantOnly` boolean query를 추가한다.
- 현재 표시 대상인 Portal 및 활성 scope에 대한 수동 허용만 필터 기준으로 사용한다.
- 권한 매트릭스 필터 바에 체크박스를 추가한다.
- DB schema, migration, auth 규칙, 다른 권한 목록 API는 변경하지 않는다.

## 설계
- serializer가 `manualGrantOnly`를 boolean으로 검증하고 view가 service에 전달한다.
- service는 표시 대상 scope ID와 함께 selector에 필터 조건을 전달한 뒤 pagination한다.
- selector는 `access_grants` 중 `status=allowed`이고 표시 대상 scope에 속하는 행이 존재하는 사용자만 중복 없이 반환한다.
- 프론트엔드는 filter draft와 적용 filter에 boolean 값을 보관하고 React Query key 및 API query에 포함한다.
- 체크박스는 기존 검색/초기화 흐름을 따르며 즉시 조회하지 않고 검색 버튼으로 적용한다.

## 실행 단계
- [x] API query serializer, view, service, selector를 연결한다.
- [x] 수동 허용·대기·차단·비표시 scope 조건을 검증하는 backend 테스트를 추가한다.
- [x] 프론트엔드 API hook과 matrix filter state에 `manualGrantOnly`를 연결한다.
- [x] 필터 바에 접근 가능한 체크박스를 추가하고 초기화 동작을 맞춘다.
- [x] backend container 테스트와 frontend lint/audit를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account.tests.AccountAccessManagementApiTests`
- `npm --prefix apps/web run lint`
- `scripts/agent/check_backend_boundaries.sh`
- `scripts/agent/check_ui_consistency.sh`
- 기대 결과: 추가 테스트와 lint가 통과하고, 감사 스크립트에는 이번 변경으로 생긴 신규 위반이 없다.

## 위험과 대응
- 위험: 비활성 scope의 과거 수동 권한 때문에 사용자가 필터 결과에 포함될 수 있다.
- 대응: service가 현재 표시 scope ID를 selector에 전달해 범위를 제한한다.
- 위험: relation join으로 사용자 중복이 발생할 수 있다.
- 대응: selector 결과에 `distinct()`를 적용한 뒤 pagination한다.

## 진행 기록
- 2026-07-29: `manualGrantOnly=true` 계약과 표시 대상 scope 기준을 확정했다.
- 2026-07-29: backend 필터와 회귀 테스트, frontend 체크박스 및 query 연결을 완료했다.
- 2026-07-29: Docker backend 테스트 3개, frontend ESLint, diff 검사, backend boundary audit가 통과했다. UI 감사는 기존 `l3-spider` 후보만 보고했다.
