# 02. Keycloak 환경변수 안내

[시작 안내](../README.md) · [단계별 실행](../04_SETUP_FLOW.md)

필요한 값은 **서버 기동용**, **사내 IdP 연결용**, **Portal 앱용**, **SDWT 관리자용**으로 구분합니다.
실행할 단계에 해당하는 입력만 준비합니다.

## 입력 위치

| 작업 | 입력 위치 | 적용 명령 |
| --- | --- | --- |
| 서버 기동 | `deploy/keycloak/env/prod.env` | `keycloak-check`, `keycloak-up` |
| 0. Realm / 2. User Profile / 3. IdP mapper | 기존 `etch-sso/keycloak-runtime` Secret의 관리자 계정 | 해당 단계별 Make 명령 |
| 1. 사내 IdP | `deploy/keycloak/env/prod.env`의 `CORP_OIDC_*` | `keycloak-idp-setup` |
| 4. Portal client | `deploy/portal/env/prod/api.env` | `keycloak-portal-client-setup` |
| 5. SDWT | 관리자 인증 환경변수 + CSV 경로 | `keycloak-sdwt-init` |

## 서버 기동용 값

| Keycloak `prod.env` 항목 | 의미 |
| --- | --- |
| `postgres-password` | Keycloak PostgreSQL 비밀번호 |
| `bootstrap-admin-username` | 최초 관리자 계정이며 설정 Job의 로그인 계정으로도 사용 |
| `bootstrap-admin-password` | 관리자 비밀번호. 운영 중에는 실제 관리자 비밀번호와 일치해야 함 |
| `keycloak-public-url` | 공개 HTTPS URL. 경로와 끝의 `/` 없음 |

```bash
chmod 600 deploy/keycloak/env/prod.env
make env-check APP=keycloak PROFILE=prod COMPONENT=server
```

서버 기동에는 사내 client나 Portal client 입력이 필요하지 않습니다.
서버·TLS Secret 최초 준비는 [서버 설치](../01_SERVER_SETUP.md)의 `keycloak-check` → `keycloak-up`을 사용합니다.

## 사내 Identity Provider용 값

| Keycloak `prod.env` 항목 | 의미 |
| --- | --- |
| `CORP_OIDC_DISCOVERY_URL` | 사내 metadata URL. 현재 파일에 설정돼 있음 |
| `CORP_OIDC_CLIENT_ID` | AD FS에서 발급받은 client ID |
| `CORP_OIDC_CLIENT_SECRET` | 해당 client의 secret |
| `CORP_OIDC_CLIENT_AUTH_METHOD` | 현재 확인된 방식은 `client_secret_post` (request body) |
| `CORP_OIDC_VALIDATE_SIGNATURE` | `true` |

운영 서버에서는 기존 provider의 client ID·secret을 입력합니다.
Authorization·Token·JWKS·UserInfo·Logout URL과 issuer는 별도 입력하지 않습니다.
Discovery가 제공하는 값은 실행 시 해석하고 원본 env를 덮어쓰지 않습니다.
선택 endpoint가 제공되지 않을 때의 처리는 [Discovery 안내](../05_DISCOVERY_SETUP.md)에 있습니다.

## Portal 앱용 값

Portal은 AD FS에 연결하는 client와 별개의 Keycloak client입니다.
`deploy/portal/env/prod/api.env`에 `OIDC_PROVIDER=keycloak`, `OIDC_CLIENT_ID`,
`OIDC_CLIENT_SECRET`, `OIDC_ISSUER`, `OIDC_REDIRECT_URI`, `FRONTEND_BASE_URL`을 준비합니다.
상세 값과 갱신 범위는 [Portal client 등록 계약](../../portal/k8s/jobs/keycloak-client/README.md)을 따릅니다.

`KEYCLOAK_PORTAL_ENV`는 위 파일을 선택하는 **Make 인자**입니다. 사내 env에 넣는 항목이 아닙니다.
기본 파일 대신 다른 파일을 사용할 때 단계별 명령에 경로를 지정합니다.

## SDWT 관리자 인증

5번은 관리자 접속 URL·계정·비밀번호 또는 서비스 계정을 환경변수로 받습니다.
`keycloak-runtime` Secret을 자동으로 읽지 않습니다. [SDWT 연결과 인증](../07_SDWT_SETUP.md#2-연결과-인증)을 따릅니다.

## 파일 작성과 반영의 차이

- env는 `KEY=값` 형식입니다. 값에 shell 명령이나 따옴표 감싸기를 사용하지 않습니다. 파일을 shell 코드로 실행하지 않습니다.
- 저장소 규칙에 따라 운영 설정·credential은 하나의 `prod.env`로 관리하며 private Git에 포함합니다. 인증서·개인키와 실제 사용자 CSV는 별도 정책을 따릅니다.
- 파일만 수정하면 Kubernetes Secret·DB 비밀번호·기존 Keycloak 설정은 바뀌지 않습니다.
- 서버 도구는 기존 Secret과 입력이 다르면 중단합니다. DB나 관리자 비밀번호 변경은 해당 실제 서비스와 Secret을 함께 맞춰야 합니다.

| 보조 명령 | 수행하는 일 |
| --- | --- |
| `make env-check APP=keycloak PROFILE=prod COMPONENT=oidc` | Discovery 해석과 입력 검사만 수행 |
| `make k8s-env APP=keycloak PROFILE=prod COMPONENT=oidc` | 해석된 값을 OIDC Secret에 등록. Job은 실행하지 않음 |
| `make env-profile-key-check ENV_APP=keycloak ENV_PROFILE=prod` | env 파일의 구조 검사 |

보조 Secret 명령은 현재 kubectl context를 사용합니다. 보통은 context를 명시하는
[단계별 명령](../04_SETUP_FLOW.md)을 사용하세요. Discovery 입력이 없는 별도 수동 env는 기존 명시적 endpoint 입력도 지원합니다.
