# Keycloak 환경설정 입력 폴더

프로젝트를 서버에 복사한 뒤 이 폴더의 `prod.env`에 실제 값을 입력합니다.
기존 배포 도구가 기본으로 읽는 위치이므로 별도 경로 설정이 필요하지 않습니다.
실제 env와 백업 파일은 Git에서 제외합니다. Git clone으로 가져온 경우 아래처럼 생성합니다.

저장소 루트에서 실행합니다. 기존 파일은 덮어쓰지 않습니다.

```bash
test -f deploy/keycloak/env/prod.env || \
  install -m 0600 deploy/keycloak/env/prod.env.example deploy/keycloak/env/prod.env
vi deploy/keycloak/env/prod.env
make env-check APP=keycloak PROFILE=prod COMPONENT=server
```

| 항목 | 입력 내용 |
| --- | --- |
| `postgres-password` | Keycloak PostgreSQL 비밀번호 |
| `bootstrap-admin-username` | 빈 DB 최초 기동 시 만들 관리자 계정 |
| `bootstrap-admin-password` | 초기 관리자 비밀번호 |
| `keycloak-public-url` | 공개 URL. 현재 원본 기준 `https://etch-sso.samsungds.net`, 끝에 `/` 없음 |
| `CORP_OIDC_*` | 사내 로그인 연결을 등록할 때 필요한 발급값·endpoint |

값은 예시 파일의 `KEY=값` 형식을 따릅니다. 실제 비밀값은 예시 파일에 넣지 않습니다.
서버 구동에는 첫 네 항목이 필요하고, 빈 DB에 사내 로그인을 연결하려면 `CORP_OIDC_*`도 준비합니다.
파일을 수정한 것만으로 Kubernetes Secret이나 기존 DB 비밀번호가 변경되지는 않습니다.

TLS 입력은 [인증서 폴더](../certs/README.md)를 참고합니다.
Secret 최초 등록·배포는 [Keycloak 배포 안내](../README.md)의 `make keycloak-check`와
`make keycloak-up`을 사용합니다. 이미 있는 Secret을 의도적으로 갱신할 때만 별도 등록 절차를 사용합니다.
