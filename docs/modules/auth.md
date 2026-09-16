# Auth 모듈

Auth는 OIDC 기반 로그인과 Django session 관리를 담당합니다.

## 기능 요약

- OIDC 로그인 시작
- OIDC callback 처리
- 사용자 생성/갱신
- Django session login/logout
- 현재 사용자 정보 조회
- redirect target 검증

## 동작 흐름

1. 프론트가 로그인 endpoint를 호출합니다.
2. 서버가 canonical `target`을 검증하고 state와 nonce를 생성합니다.
3. 사용자는 설정된 ADFS 또는 Keycloak authorize URL로 이동합니다.
4. ADFS는 callback에 `id_token`을 전달하고, Keycloak은 PKCE로 보호된 code를 전달합니다.
5. Keycloak code는 내부 token endpoint에서 id_token으로 교환합니다.
6. 서버가 state, nonce와 provider별 token 검증 조건을 확인합니다.
7. claim을 정규화한 뒤 Account service facade로 `User`를 생성하거나 갱신합니다.
8. Django session을 만들고 프론트로 redirect합니다.

## Account와의 연결

로그인 후 `/api/v1/auth/me`는 사용자 정보와 소속 상태를 반환합니다. 프론트는 이 값으로 온보딩 또는 소속 재확인 dialog를 띄울지 결정합니다.

## 로컬 개발

로컬에서는 `local/adfs_dummy`가 ADFS 역할을 하며 discovery가 노출하는 authorize/token/userinfo endpoint를 모두 제공합니다.
로컬 Kubernetes에서는 login-only Keycloak을 kind 안에 배포합니다. Keycloak의 role/group을
Portal 권한 원천으로 사용하지 않으며 기존 Django `scopeAccess`가 계속 권한을 판정합니다.

## 화면/API/데이터 추적

| 구간 | 위치 |
| --- | --- |
| 화면 | `/login`, 인증 후 `/` |
| Frontend | `apps/portal/web/src/features/auth` |
| Backend API | `/api/v1/auth/config`, `/api/v1/auth/login`, `/api/v1/auth/me`, `/api/v1/auth/logout`, `/auth/google/callback/`, `/auth/keycloak/callback/` |
| 데이터 | `api.account.User`, Django session |
| 외부 연동 | ADFS/OIDC 또는 `local/adfs_dummy` |

## 운영 포인트

- 로그인 redirect 오류는 `ALLOWED_REDIRECT_HOSTS`, `OIDC_REDIRECT_URI`, proxy host 설정을 확인합니다.
- ADFS callback 오류는 state/nonce/session cookie와 인증서 설정을 확인합니다.
- Keycloak callback 오류는 PKCE session, client secret, issuer와 내부 token/JWKS URL을 확인합니다.
- `/api/v1/auth/me` 응답은 Account 온보딩/소속 재확인 UI의 기준입니다.

## 관련 API

- `docs/api/auth.md`

## 관련 코드

- `apps/portal/api/api/auth/views.py`
- `apps/portal/api/api/auth/callback_urls.py`
- `apps/portal/api/api/auth/urls.py`
- `apps/portal/api/api/auth/selectors.py`
- `apps/portal/api/api/auth/services/oidc.py`
- `apps/portal/api/api/auth/services/oidc_utils.py`
- `apps/portal/api/api/auth/services/keycloak_oidc.py`
- `apps/portal/api/api/auth/services/authentication.py`
- `apps/portal/web/src/features/auth`
