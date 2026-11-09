# Auth

[문서 홈](../README.md) · [기능·API](README.md)

- [기능과 흐름](#기능과-흐름)
- [API](#api)

## 기능과 흐름


Auth는 사용자를 Keycloak 로그인 화면으로 보내고, 로그인 결과를 검증한 뒤 Portal 세션을 만듭니다.
브라우저는 이후 API 요청에 세션 쿠키를 사용합니다. Portal이 직접 지원하는 로그인 provider는 Keycloak입니다.

사용자 관점에서는 **Portal 열기 → Keycloak 로그인 → 원래 화면 복귀** 순서로 동작합니다.
아래 로그인 흐름은 이 과정의 내부 검증을 설명합니다. 화면이 열린 뒤 접근이 거부되는 문제는
[Account의 앱·데이터 권한](02-account.md#기능과-흐름)도 함께 확인합니다. [OIDC·PKCE·JWKS 용어](../concepts/01-architecture.md#로그인과-외부-연동)는 용어 안내에 있습니다.

### 로그인 흐름

1. `/api/v1/auth/login?target=/settings/account`에서 복귀 주소를 검증합니다.
2. 무작위 일회용 state, nonce, 복귀 주소와 PKCE verifier를 서버 세션에 저장합니다.
3. 브라우저가 Keycloak authorize endpoint로 이동합니다.
4. `/auth/keycloak/callback/`에서 state를 확인하고 code를 token endpoint에서 교환합니다.
5. JWKS 서명, issuer, audience, token 시간과 nonce 및 필수 신원을 검증합니다.
6. EPID 계정을 생성·갱신하고 검증된 앱 역할·SDWT 그룹을 로그인 세션에 저장합니다.
7. Django 세션으로 로그인한 뒤 저장한 복귀 주소로 이동합니다.

### 권한과 계정

`/api/v1/auth/me`는 현재 세션의 `scopeAccess`, `sdwtAccess`, 소속과 신원 정보를 반환합니다.
Keycloak 역할·그룹 변경은 재로그인 후 반영됩니다. DB 소속·권한 행이나 Django 관리자 플래그는
로그인 권한의 원천이 아닙니다. 세부 규칙은 [Account 모듈](02-account.md#기능과-흐름)을 봅니다.

### 로컬 개발과 운영

로컬 Kubernetes는 `local/keycloak`을 사용하며 `local/adfs_dummy`는 upstream IdP와 업무 외부계를 대체합니다.

로그인 오류는 `OIDC_*`, `ALLOWED_REDIRECT_HOSTS`, 세션 cookie, PKCE, issuer와 token/JWKS 접근 경로를 확인합니다.
Callback 검증 실패는 프론트 복귀 URL의 `error` query로 전달됩니다.

### 관련 코드와 API

- [Auth API](#api)
- `apps/portal/api/api/auth/callback_urls.py`
- `apps/portal/api/api/auth/views.py`
- `apps/portal/api/api/auth/services/oidc.py`
- `apps/portal/api/api/auth/services/keycloak_oidc.py`
- `apps/portal/api/api/auth/services/authentication.py`
- `apps/portal/api/api/account/services/keycloak_access.py`

## API


Keycloak OIDC authorization code + PKCE와 Django 세션을 사용합니다.

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/v1/auth/config` | 공개 OIDC 설정과 `authorizationSource: keycloak` |
| GET | `/api/v1/auth/login?target=/settings/account` | 로그인 시작 |
| GET | `/auth/keycloak/callback/?code=<code>&state=<state>` | 일회용 code callback |
| GET | `/api/v1/auth/me` | 로그인 사용자의 현재 세션 정보 |
| GET | `/api/v1/auth/logout` | 세션 종료 후 Keycloak logout redirect |
| POST | `/api/v1/auth/logout` | 세션 종료 후 `logoutUrl` JSON 반환 |
| GET | `/api/v1/auth/?target=/settings/account` | 프론트 복귀 주소로 redirect |

### 로그인과 callback

로그인 query는 `target`만 받습니다. `next` 등 미지원 필드는 400입니다.
서버가 복귀 주소를 검증하고 일회용 state·nonce와 PKCE 정보를 세션에 저장합니다.
State는 복귀 주소를 인코딩한 문자열이 아닙니다.

Callback은 GET만 받습니다. State, PKCE code 교환, JWKS 서명, issuer, audience, token 시간,
nonce와 신원을 검증한 뒤 사용자와 권한 snapshot을 세션에 저장합니다.
기존 `/auth/google/callback/`은 제공하지 않습니다.

### 현재 사용자

`GET /api/v1/auth/me`의 주요 필드는 다음과 같습니다.

| 필드 | 의미 |
| --- | --- |
| `id`, `knoxId`, `avatarId`, `username`, `email` | 사용자 식별 정보 (`avatarId`는 EPID) |
| `department`, `line`, `userSdwtProd` | 현재 로그인 세션의 소속 |
| `authorizationSource` | `keycloak` |
| `hasAllAppsAccess`, `isPortalAdmin` | 세션의 전체 앱·Portal 관리자 역할 |
| `scopeAccess` | scope별 `allowed`, `role`, `source` 등 접근 정보 |
| `sdwtAccess` | SDWT 이름을 키로 하는 `viewer`/`user`/`admin` 등급 |
| `pendingUserSdwtProd`, `hasPendingAffiliation` | 호환 응답 값 `null`, `false` |

조회는 DB 소속을 자동 생성하거나 세션 권한을 갱신하지 않습니다. 역할 변경 후 재로그인이 필요합니다.

### 오류

| 응답 | 상황 |
| --- | --- |
| 400 | 로그인·프론트 redirect의 미지원 query |
| 401 | 로그인하지 않은 `/me` 요청 |
| 405 | GET 이외 callback 요청 |
| 503 | OIDC provider 설정 누락 |
| 302 + `error` query | callback state/code/token/nonce/신원 검증 실패 |

관련 문서: [Auth 모듈](#기능과-흐름), [Account 권한](02-account.md#기능과-흐름).
