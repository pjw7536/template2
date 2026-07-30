# ExecPlan: 전체 권한 승인 대기 및 일괄 승인

## 목표
- Portal 관리자가 모든 앱·기능의 승인 대기 요청을 한 목록에서 확인한다.
- 전체 목록을 기본으로 제공하면서 기존 앱별 필터를 유지한다.
- 현재 페이지에서 명시적으로 선택한 요청을 일반 사용자 역할로 일괄 승인한다.

## 현재 상태
- `apps/web/src/features/account/pages/PermissionsPage.jsx`는 승인 대기 조회 범위를 `portal`로 초기화한다.
- 기존 `/api/v1/account/access/users` API는 사용자와 단일 scope의 최종 권한 상태를 조회한다.
- 같은 사용자의 Portal·앱 요청은 `account_user_access`의 서로 다른 행으로 저장된다.
- `apps/web/src/features/account/components/ScopePermissionMatrix.jsx`에는 사용자의 미커밋 역할 색상 변경이 있으며 보존한다.

## 범위
- account 도메인에 전체 승인 대기 조회와 선택 요청 일괄 승인 API를 추가한다.
- 승인 대기 화면에 전체/앱 필터, 신청 앱 열, 현재 페이지 선택 체크박스와 확인 대화상자를 추가한다.
- dev 통합 시드에 권한 관리 화면 검증용 account 사용자와 요청 상태를 추가한다.
- 단건 승인·거절 및 기존 권한 매트릭스 API 계약은 유지한다.
- DB schema, migration, 외부 인증/OIDC, Compose/env 계약은 변경하지 않는다.

## 설계
- 전체 승인 대기 조회는 `UserAccess.status=pending` 행을 요청 시각 역순으로 페이지네이션한다.
- 각 결과는 `requestId`, `scope`, `user`, `access`를 포함하며 앱별/전체 건수를 함께 반환한다.
- 일괄 승인 입력은 최대 100개의 `requestIds`로 제한하고 중복을 제거한다.
- 각 요청은 기존 canonical 단건 승인 함수를 통해 감사 로그를 남기며, 일부 요청이 이미 처리된 경우 성공·실패 결과를 구분한다.
- 일괄 승인은 권한 승격 위험을 줄이기 위해 `user` 역할로 고정한다.
- 프런트엔드는 현재 페이지 선택만 지원하며 필터나 페이지가 바뀌면 선택을 초기화한다.
- account dev 시드는 24명의 승인 대기 사용자와 4명의 상태 비교 사용자를 prefix로 격리해 생성한다.
- offsite 인증/mock과 외부 URL 계약에는 영향이 없다.

## 실행 단계
- [x] 전체 승인 대기 selector/service/serializer/view/URL과 테스트 추가
- [x] 선택 요청 일괄 승인 service/API와 정상·부분 실패·권한 테스트 추가
- [x] React Query API/hook 및 public export 추가
- [x] 승인 대기 전체/앱 필터와 선택 일괄 승인 UI 추가
- [x] 백엔드·프런트엔드 검증 실행
- [x] dev 통합 시드에 account 권한 요청 더미데이터와 회귀 테스트 추가

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py seed_dev_data --reset --skip-rag --prefix DEV`
- `npm --prefix apps/web run lint`
- `npm --prefix apps/web run build`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:ui`

## 위험과 대응
- 위험: 동일 사용자의 여러 scope 요청을 하나로 합쳐 승인 단위가 모호해질 수 있다.
- 대응: `requestId`별 행과 선택 상태를 유지하고 scope를 항상 표시한다.
- 위험: 목록 조회 후 다른 관리자가 먼저 처리한 요청을 다시 승인할 수 있다.
- 대응: canonical 상태 전이 검증 결과를 개별 실패로 반환하고 최신 목록을 다시 조회한다.
- 위험: Portal과 앱 요청의 승인 순서 때문에 앱이 일시적으로 Portal에 차단될 수 있다.
- 대응: 같은 사용자의 Portal 요청을 앱 요청보다 먼저 처리하되 각 요청은 독립 결과로 기록한다.

## 진행 기록
- 2026-07-28: 전체 요청 기본 보기와 체크박스 기반 선택 일괄 승인을 설계했다.
- 2026-07-28: account 테스트 161개, migration check, frontend lint/build, frontend/backend boundary 감사를 통과했다.
- 2026-07-28: UI 감사의 기존 L3 Spider raw chart 색상 후보는 요청 범위 밖으로 유지했다.
- 2026-07-28: 웹에서 승인 대기/일괄 승인/권한 매트릭스를 확인할 account dev 시드 추가를 시작했다.
- 2026-07-28: account/management 171개 테스트, migration check, backend boundary 감사를 통과하고 개발 DB에 28명·대기 54건을 적재했다.
