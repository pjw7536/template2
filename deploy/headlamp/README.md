# Headlamp 배포

[전체 배포](../README.md) · [공통 준비](../shared/docs/README.md)

Keycloak로 로그인한 사용자의 그룹을 Kubernetes RBAC에 연결하는 관리 화면입니다.

| 순서 | 작업 |
| --- | --- |
| 1 | [서버·입력·TLS·CA 준비](docs/01-prepare.md) |
| 2 | [Keycloak client·관리자 그룹·모든 API server의 OIDC 설정](docs/02-authentication.md) |
| 3 | [배포·HTTPS·로그인·권한 검증](docs/03-deploy.md) |
| 4 | [Secret·CA 갱신·재설치·복구](docs/04-operations.md) |

허용한 `headlamp-admins` 그룹은 cluster-admin 권한을 가집니다. client 등록과 Pod Ready 외에 모든 API server의 인증 반영을 확인해야 합니다.
