# Keycloak 환경설정 입력 폴더

일반 설정은 Git에 포함된 `prod.env`, 비밀값은 Git에서 제외하는 `prod.secrets.env`에 저장합니다.
기존 배포 도구가 두 파일을 자동 병합하므로 별도 경로 설정은 필요하지 않습니다.

새 서버에는 기존 비밀값 파일을 같은 폴더에 복사한 뒤 검사합니다.

```bash
chmod 600 deploy/keycloak/env/prod.secrets.env
make env-check APP=keycloak PROFILE=prod COMPONENT=server
```

`prod.secrets.env`에는 `postgres-password`, `bootstrap-admin-password`,
`CORP_OIDC_CLIENT_SECRET`을 `KEY=값` 형식으로 넣습니다. 일반 env의 해당 키는 비워둡니다.

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

TLS 입력은 [인증서 폴더](../../shared/certs/README.md)를 참고합니다.
Secret 최초 등록·배포는 [Keycloak 배포 안내](../README.md)의 `make keycloak-check`와
`make keycloak-up`을 사용합니다. 이미 있는 Secret을 의도적으로 갱신할 때만 별도 등록 절차를 사용합니다.
