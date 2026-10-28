# Auth 모듈

Auth는 Keycloak OIDC 로그인과 Django 세션을 관리합니다. Portal이 직접 지원하는 provider는 Keycloak뿐입니다.

## 로그인 흐름

1. `/api/v1/auth/login?target=/settings/account`에서 복귀 주소를 검증합니다.
2. 무작위 일회용 state, nonce, 복귀 주소와 PKCE verifier를 서버 세션에 저장합니다.
3. 브라우저가 Keycloak authorize endpoint로 이동합니다.
4. `/auth/keycloak/callback/`에서 state를 확인하고 code를 token endpoint에서 교환합니다.
5. JWKS 서명, issuer, audience, token 시간과 nonce 및 필수 신원을 검증합니다.
6. EPID 계정을 생성·갱신하고 검증된 앱 역할·SDWT 그룹을 로그인 세션에 저장합니다.
7. Django 세션으로 로그인한 뒤 저장한 복귀 주소로 이동합니다.

## 권한과 계정

`/api/v1/auth/me`는 현재 세션의 `scopeAccess`, `sdwtAccess`, 소속과 신원 정보를 반환합니다.
Keycloak 역할·그룹 변경은 재로그인 후 반영됩니다. DB 소속·권한 행이나 Django 관리자 플래그는
로그인 권한의 원천이 아닙니다. 세부 규칙은 [Account 모듈](account.md)을 봅니다.

## 로컬 개발과 운영

로컬 Kubernetes는 `local/keycloak`을 사용하며 `local/adfs_dummy`는 upstream IdP와 업무 외부계를 대체합니다.
Portal의 직접 ADFS form_post callback은 제거됐습니다.

로그인 오류는 `OIDC_*`, `ALLOWED_REDIRECT_HOSTS`, 세션 cookie, PKCE, issuer와 token/JWKS 접근 경로를 확인합니다.
Callback 검증 실패는 프론트 복귀 URL의 `error` query로 전달됩니다.

## 관련 코드와 API

- [Auth API](../api/auth.md)
- `apps/portal/api/api/auth/callback_urls.py`
- `apps/portal/api/api/auth/views.py`
- `apps/portal/api/api/auth/services/oidc.py`
- `apps/portal/api/api/auth/services/keycloak_oidc.py`
- `apps/portal/api/api/auth/services/authentication.py`
- `apps/portal/api/api/account/services/keycloak_access.py`
