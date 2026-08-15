# ExecPlan: Work Hub 기준선과 Keycloak 권한 전환

## 목표
- 최신 `stash@{0}`의 Work Hub 변경을 전용 브랜치에서 복원하고 검증한 별도 커밋으로 확정한다.
- 검증된 Work Hub 커밋에서 새 브랜치를 만들어 인증과 권한 원천을 Keycloak group/client role로 전환한다.
- Account에는 `User` shadow와 읽기 전용 내 정보 표면만 남기고, Work Hub 및 Grist ACL을 Keycloak 기준으로 동기화한다.

## 현재 상태
- Work Hub 기준선은 `feat/work-hub-baseline`의 `3c6b8553` 커밋으로 확정됐다.
- Keycloak 전환 구현과 검증은 `feat/keycloak-auth-migration`에서 진행한다.
- `stash@{0}`과 이전 stash는 삭제하지 않았고 `data/work_hub_secrets/dev/grist_api_key`는 추적하지 않는다.
- 실제 운영 DB/realm cutover와 non-User Account 테이블 삭제는 복구 증적을 요구하는 운영 gate 뒤에서만 실행한다.

## 범위
- 수정: `apps/api`의 auth/account/work_hub, 관련 테스트·migration·관리 명령.
- 수정: `apps/web`의 Work Hub launcher와 `/settings/account` 읽기 전용 화면.
- 수정: dev/oidc/prod Compose, env 예시, Keycloak/로컬 mock wiring, 운영·이관 문서.
- 제외: 실제 운영 Keycloak 변경, 실제 credential 생성·회전, 실제 운영 DB 삭제/전환 실행.

## 설계
- 브랜치 순서: `main` → `feat/work-hub-baseline` → Work Hub 커밋 → `feat/keycloak-auth-migration`.
- 인증: 사내 OIDC를 Keycloak upstream IdP로 두고 Portal은 Keycloak authorization code flow/JWKS를 사용해 Django session을 만든다.
- 권한: realm group `/affiliations/<소속>/<viewer|member|manager>`와 client role `portal-user/admin`, `<scope>-user/admin`을 정규화된 런타임 principal로 변환한다.
- 데이터: Work Hub 문서는 `Affiliation` FK 대신 `keycloak_group_id`와 표시용 소속 snapshot을 저장한다.
- Grist: 읽기 전용 Admin API service account로 멤버십을 조회하고 5분 이내 reconciliation하며 장기 실패 시 접근을 fail-closed 처리한다.
- 이관: 현재 유효한 기본 소속과 Portal·앱 user/admin 권한만 dry-run/멱등 방식으로 내보내며 누락·중복을 차단한다.
- 제거: 검증 후 Account non-User 테이블과 쓰기 API/관리 UI를 새 migration 및 코드 삭제로 제거하고 `/settings/account`는 읽기 전용으로 유지한다.

## 실행 단계
- [x] `feat/work-hub-baseline`을 만들고 `git stash apply stash@{0}`으로 최신 stash만 복원한다.
- [x] 비밀 파일을 staging에서 제외하고 Work Hub 코드/계약을 검토·보완한다.
- [x] Work Hub backend/frontend/Compose와 ACL/Webhook/forward-auth/worker 및 경계 audit를 검증한다.
- [x] Work Hub 기준선을 별도 커밋으로 확정하되 stash는 유지한다.
- [x] 기준선 커밋에서 `feat/keycloak-auth-migration` 브랜치를 만든다.
- [x] Keycloak 인증, role/group 해석, shadow User 동기화와 로컬 Compose를 구현한다.
- [x] Work Hub schema와 Grist ACL reconciliation을 Keycloak 기준으로 전환한다.
- [x] legacy 권한 이관/비교/backup/realm export·restore 검증 도구를 구현한다.
- [x] Account 쓰기 API·관리 UI를 제거하고 읽기 전용 계정 화면을 유지한다.
- [ ] 실제 운영 cutover 증적 확인 뒤 non-User Account 모델·테이블 제거 migration을 별도 배포한다.
- [x] backend/frontend/Compose/audit 및 핵심 권한 조합 테스트를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml config`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account api.auth api.work_hub`
- frontend Work Hub/account 테스트와 build/lint(저장소 package script 기준)
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- Keycloak migration 명령의 dry-run·멱등성 및 legacy/Keycloak 비교 테스트
- Compose 기반 code flow/JWKS/refresh 및 Grist role 회수/fail-closed 통합 점검

## 위험과 대응
- 위험: stash의 credential이 실수로 커밋될 수 있다.
- 대응: 경로를 ignore하고 `git diff --cached` 및 커밋 트리를 명시적으로 검사한다.
- 위험: Account 제거가 기존 feature의 import/권한 계약을 깨뜨릴 수 있다.
- 대응: public facade 사용처를 먼저 열거하고 단계별 migration과 전체 경계 audit를 수행한다.
- 위험: 운영 식별자·비상 계정이 현재 저장소에 없다.
- 대응: env/명령 인자로 강제하고 실제 cutover 명령은 값 누락 시 실패하도록 만든다.
- 위험: 외부망에서 corporate OIDC/운영 Keycloak을 사용할 수 없다.
- 대응: 로컬 Keycloak과 전용 PostgreSQL, import 가능한 realm 구성을 Compose에 제공한다.

## 진행 기록
- 2026-08-14: 사용자 제공 계획과 저장소 규칙을 기준으로 ExecPlan을 생성했다.
- 2026-08-14: `stash@{0}`을 `feat/work-hub-baseline`에 적용하고 secret 제외, 407개 backend 테스트, frontend test/build/lint, Compose config, migration drift, 전체 agent audit를 통과했다.
- 2026-08-14: Work Hub 기준선을 `3c6b8553`으로 커밋하고 `feat/keycloak-auth-migration` 브랜치를 생성했다. stash는 삭제하지 않았다.
- 2026-08-14: Keycloak 26.7.1 code flow/PKCE, JWKS, 300초 refresh, Django session과 Admin API ACL 투영을 로컬 Compose에서 통합 검증했다.
- 2026-08-14: Keycloak shadow data scope, app-admin 전체 범위, Grist 5분 reconciliation/fail-closed, 이관 dry-run·멱등·비교와 cutover 증적 gate를 구현했다.
- 2026-08-14: 전체 Django 930개, frontend 181개 테스트, frontend lint/build, dev/oidc/prod Compose config와 agent audit를 통과했다. 실제 운영 데이터 삭제는 운영 backup/export/restore 증적 전이므로 실행하지 않았다.
