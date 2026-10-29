# Auth API

[API 공통 규칙·목록](README.md) · [문서 홈](../README.md) · [기능·데이터 설명](../modules/01-auth.md)

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

## 로그인과 callback

로그인 query는 `target`만 받습니다. `next` 등 미지원 필드는 400입니다.
서버가 복귀 주소를 검증하고 일회용 state·nonce와 PKCE 정보를 세션에 저장합니다.
State는 복귀 주소를 인코딩한 문자열이 아닙니다.

Callback은 GET만 받습니다. State, PKCE code 교환, JWKS 서명, issuer, audience, token 시간,
nonce와 신원을 검증한 뒤 사용자와 권한 snapshot을 세션에 저장합니다.
기존 `/auth/google/callback/`은 제공하지 않습니다.

## 현재 사용자

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

## 오류

| 응답 | 상황 |
| --- | --- |
| 400 | 로그인·프론트 redirect의 미지원 query |
| 401 | 로그인하지 않은 `/me` 요청 |
| 405 | GET 이외 callback 요청 |
| 503 | OIDC provider 설정 누락 |
| 302 + `error` query | callback state/code/token/nonce/신원 검증 실패 |

관련 문서: [Auth 모듈](../modules/01-auth.md), [Account 권한](../modules/02-account.md).
