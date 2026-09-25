# 02. Keycloak 최초 설치 입력

[전체 설치 순서](../README.md) · 실행: [서버 설치](../01_SERVER_SETUP.md) / [Keycloak 자체 설정](../04_SETUP_FLOW.md)

이 문서는 입력 위치와 의미만 설명합니다. 파일 편집·검사·적용 명령은 실행 문서를 따릅니다.
설정 파일은 `KEY=값` 형식이며 셸 코드로 `source`하지 않습니다. 값을 따옴표로 감싸지 않습니다.

## 서버 기동용 값

`deploy/keycloak/env/prod.env`에 입력합니다.

| 항목 | 의미 |
| --- | --- |
| `postgres-password` | 새 Keycloak PostgreSQL의 비밀번호 |
| `bootstrap-admin-username` | 최초 관리자 계정 |
| `bootstrap-admin-password` | 최초 관리자 비밀번호. 설정 Job도 같은 계정 사용 |
| `keycloak-public-url` | 공개 HTTPS URL. 경로와 끝의 `/` 없음 |

서버 설치 도구가 `etch-sso/keycloak-runtime` Secret을 준비합니다.
Realm·프로필·IdP mapper Job은 이 Secret으로 인증하므로 별도 관리자 값을 입력하지 않습니다.

## 사내 Identity Provider용 값

같은 `deploy/keycloak/env/prod.env`에 입력합니다. 사내 AD FS에서 발급받은 client를 사용합니다.

| 항목 | 입력 |
| --- | --- |
| `CORP_OIDC_DISCOVERY_URL` | 사내 metadata URL. 저장소 파일에 설정돼 있으므로 대상 주소 확인 |
| `CORP_OIDC_CLIENT_ID` | 사내 client ID |
| `CORP_OIDC_CLIENT_SECRET` | 사내 client secret |
| `CORP_OIDC_CLIENT_AUTH_METHOD` | `client_secret_post` |
| `CORP_OIDC_VALIDATE_SIGNATURE` | `true` |

Authorization·Token·JWKS·UserInfo·Logout URL과 issuer는 별도로 입력하지 않습니다.
[Discovery](../05_DISCOVERY_SETUP.md)가 제공하는 값을 해석합니다.
사내 client의 redirect URI는 `<공개 Keycloak URL>/realms/etch/broker/oidc/endpoint`입니다.

## SDWT 관리자 인증

SDWT 등록은 [07 연결과 인증](../07_SDWT_SETUP.md#2-연결과-인증)의 환경변수와 CSV를 사용합니다.
관리자 API 도구는 Kubernetes Secret을 자동으로 읽지 않습니다.

## 앱 입력은 Keycloak 준비 후 작성

Portal은 `deploy/portal/env/prod/api.env`, Headlamp는 `deploy/headlamp/env/k8s.env`와 전용 Secret을 사용합니다.
이 값은 Keycloak 서버 설치 입력이 아닙니다. [09 앱 연결](../09_APP_CONNECTIONS.md)에서 각 앱의 안내를 따릅니다.
사내 IdP와 업무 앱에 같은 client ID·secret을 사용하는 것으로 가정하지 않습니다.

## 파일과 적용의 차이

설정 파일만 편집하면 서버가 바뀌지 않습니다. 실행 문서의 검사·적용 명령이 Secret과 설정 Job을 준비합니다.
인증서·개인키는 [TLS 준비](../03_TLS.md)의 파일 경로를 사용합니다.
