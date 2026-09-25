# Keycloak 환경설정 입력 폴더

일반 설정과 비밀번호·사내 OIDC credential을 모두 `prod.env`에 저장하고 private Git 저장소에 포함합니다.
배포 도구는 지정한 env 하나만 읽습니다.

```bash
chmod 600 deploy/keycloak/env/prod.env
make env-check APP=keycloak PROFILE=prod COMPONENT=server
```

`postgres-password`, `bootstrap-admin-password`, `CORP_OIDC_CLIENT_SECRET`도 같은 파일에 `KEY=값`으로 입력합니다.

| 항목 | 입력 내용 |
| --- | --- |
| `postgres-password` | Keycloak PostgreSQL 비밀번호 |
| `bootstrap-admin-username` | 빈 DB 최초 기동 시 만들 관리자 계정 |
| `bootstrap-admin-password` | 초기 관리자 비밀번호 |
| `keycloak-public-url` | 공개 URL. 현재 원본 기준 `https://etch-sso.samsungds.net`, 끝에 `/` 없음 |
| `CORP_OIDC_CLIENT_ID`, `CORP_OIDC_CLIENT_SECRET` | 사내 로그인 client 발급 정보 |
| `CORP_OIDC_CLIENT_AUTH_METHOD` | 현재 provider에서 확인한 `client_secret_post` (request body 방식) |
| `CORP_OIDC_VALIDATE_SIGNATURE` | 서명 검증 사용: `true` |
| `CORP_OIDC_DISCOVERY_URL` | Discovery 설정 흐름에서 읽을 metadata URL. endpoint들은 실행 시 해석하며 파일을 덮어쓰지 않음 |

Discovery 기반 초기 설정은 [전체 설정 흐름](../DISCOVERY_SETUP.md)을 따릅니다.
Authorization·Token·JWKS·UserInfo·Logout URL과 issuer는 운영 env에 중복 입력하지 않습니다.
`make keycloak-oidc-check KUBE_CONTEXT=...`와 `make keycloak-oidc-setup KUBE_CONTEXT=...`이
discovery를 조회해 기존 Job에 필요한 endpoint 입력을 자동 생성합니다.
`make env-check APP=keycloak PROFILE=prod COMPONENT=oidc`와
`make k8s-env APP=keycloak PROFILE=prod COMPONENT=oidc`도 discovery 입력을 해석합니다.
각각 검사·Secret 등록만 수행하므로 전체 설정은 위의 통합 명령을 사용합니다.
Discovery 입력이 없으면 기존의 명시적 endpoint 입력도 지원합니다.

값은 `KEY=값` 형식으로 입력하고 파일 전체를 Git에서 관리합니다.
서버 구동에는 첫 네 항목이 필요하고, 빈 DB에 사내 로그인을 연결하려면 `CORP_OIDC_*`도 준비합니다.
파일을 수정한 것만으로 Kubernetes Secret이나 기존 DB 비밀번호가 변경되지는 않습니다.

TLS 입력은 [인증서 폴더](../../shared/certs/README.md)를 참고합니다.
Secret 최초 등록·배포는 [Keycloak 배포 안내](../README.md)의 `make keycloak-check`와
`make keycloak-up`을 사용합니다. 이미 있는 Secret을 의도적으로 갱신할 때만 별도 등록 절차를 사용합니다.
