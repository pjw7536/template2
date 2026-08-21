# ExecPlan: Auth OIDC·session·dummy 계약 단일화

## 목표
- OIDC/session/dummy 인증과 Account 연결, redirect 처리를 한 경로로 단일화한다.
- corporate network 없이 dev dummy login이 계속 동작하게 한다.

## 현재 상태
- Auth는 `/api/v1/auth/login|logout|me|config`, `/auth/google/callback/`과 frontend `/login`을 제공한다.
- `auth/views.py`는 redirect query에서 `target` 또는 `next`를 허용한다.
- OIDC claim→Account upsert가 여러 service/selectors에 나뉘어 있다.

## 범위
- 수정: `api.auth`, frontend auth feature, Account facade 호출, `apps/adfs_dummy`, `env/api.local.env`, Compose와 auth 문서.
- 유지: session cookie, callback `form_post`, Portal access gate, onboarding/reconfirm 사용자 흐름.
- 제외: Spider·Teamstaff access scope와 navigation.

## 설계
- redirect query는 `target`만 canonical로 허용하고 `next`는 400 `invalid_request`로 제거한다.
- redirect target은 common URL validator가 same-origin relative path 또는 설정된 frontend origin만 허용한다.
- OIDC claim validation, normalized identity, Account upsert, session login을 순서가 명확한 service pipeline으로 구성한다.
- Account 사용자/소속/scope 쓰기는 Account service facade를 통해서만 수행한다.
- `/me`는 현재 사용자와 `scopeAccess` canonical payload만 반환하며 legacy access field는 추가하지 않는다.
- dummy provider는 운영과 같은 discovery/token/userinfo/callback field를 반환하고 dev env URL만 사용한다.
- DB schema와 migration 변화는 없다.

## 실행 단계
- [x] 실제 OIDC와 dummy request/response/cookie/redirect characterization을 고정한다.
- [x] claim pipeline과 redirect validation을 service로 통합한다.
- [x] frontend와 dummy를 `target` 하나로 전환한 뒤 `next` alias를 제거한다.
- [x] Account 연동과 Portal gate 회귀를 실행한다.
- [x] offsite Compose를 corporate URL 없이 smoke test한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.auth api.account`
- dummy discovery/login/callback/logout HTTP smoke.
- frontend AuthProvider, RequireAuth, AppAccessGate, PortalAccessGate tests.
- `docker compose -f docker-compose.dev.yml config`, `npm run agent:audit`.

## 위험과 대응
- 위험: redirect 정규화 오류로 login loop나 open redirect가 발생한다.
- 대응: relative/absolute/encoded/external origin matrix test와 callback 후 session test를 둔다.
- 위험: dummy와 운영 claim이 달라진다.
- 대응: 동일 normalized identity fixture를 두 provider adapter에 적용한다.

## 의존성과 복구
- 상위 계약: [마스터 계획](repository-refactor-master-2026-08.md). Account 뒤, Activity 앞에 실행하며 offsite dummy 변경을 같은 배치로 배포한다.
- 복구: session/schema 변화가 없으므로 Auth/dummy/frontend를 함께 이전 redirect pipeline으로 되돌리고 기존 env를 재주입한다.

## 진행 기록
- 2026-08-18: `target`을 canonical redirect query로, `next`를 제거 대상으로 확정했다.
- 2026-08-18: login과 frontend redirect query를 `target` 하나로 전환하고 `next`와 알 수 없는 query를 canonical 400으로 거절했다. 상대·same-origin·외부·scheme-relative redirect 행렬을 별도 characterization test로 고정했다.
- 2026-08-18: `/me` 응답을 `knoxId`, `avatarId`, `isSuperuser`, `userSdwtProd`, `pendingUserSdwtProd`, `hasPendingAffiliation`, `scopeAccess`로 단일화하고 모든 저장소 frontend 소비자를 함께 갱신했다. 미인증·callback 누락·provider 미설정 오류도 공통 envelope로 전환했다.
- 2026-08-18: OIDC claim 정규화는 Auth에 유지하고 User 생성·갱신은 Account `upsert_user_identity` facade로 이동했다. Auth의 중복 사용자 ORM selector와 쓰기 책임을 제거했다.
- 2026-08-18: Dummy discovery URL의 host 마지막 글자가 잘리던 오류를 수정하고 실제 token/userinfo endpoint를 추가했다. dev image를 재빌드해 discovery·authorize·token·userinfo·logout을 각각 200/302로 smoke 검증했고 dev/OIDC/prod Compose 병합도 통과했다.
- 2026-08-18: Auth+Account 266개 backend test, frontend 전체 188개 test·lint·production build, Django check·migration drift·권한 무결성, 전체 agent audit를 통과했다. schema와 migration 변화는 없다.
