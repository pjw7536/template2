# Keycloak 배포

[전체 배포](../README.md) · [공통 준비](../shared/docs/README.md)

namespace `etch-sso`, realm `etch`, 사내 IdP alias `oidc`를 사용하는 인증 서버입니다.

| 순서 | 작업 |
| --- | --- |
| 1 | [서버·env·TLS 준비](docs/01-prepare.md) |
| 2 | [DB·Keycloak 배포와 기동 확인](docs/02-deploy.md) |
| 3 | [사내 로그인·선택 SDWT·앱 client 연결](docs/03-configure.md) |
| 4 | [설정 반영·Git·전달 YAML](docs/04-operations.md) |
| 5 | [Discovery·claim·Kubernetes 원본 계약](docs/05-reference.md) |

Keycloak 자체 사내 로그인을 먼저 확인한 뒤 Portal·Headlamp·Airflow를 연결합니다. 최초 설치에는 Portal client secret이 필요하지 않습니다.
