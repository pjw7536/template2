# Headlamp 배포 안내

[전체 배포 안내](../README.md) · [공통 준비·운영](../shared/docs/README.md)

Keycloak로 로그인한 사용자의 권한으로 Kubernetes를 관리하는 화면입니다.
먼저 Keycloak의 `etch` realm·사내 IdP `oidc` 준비를 마치고 Account Console에서 사내 로그인을 확인합니다.
공개 접속 경로는 [서비스 원본](../shared/docs/infrastructure/services.md), 공용 TLS는 [Ingress 기준](../shared/docs/ingress/operations.md#운영-ingress-기준)을 확인합니다.

## 최초 설치 순서

파일 번호는 권장 읽기 순서입니다. 실행 명령은 각 문서의 단계와 완료 기준을 따릅니다.

| 순서 | 작업·실행 위치 | 완료 기준 |
| --- | --- | --- |
| 1 | [서버·설정 준비](docs/01-setup.md), CP1 | context·env·chart·namespace·이미지 인증 준비 |
| 2 | [환경설정](docs/02-environment.md), CP1 | 입력 형식·변수 의미·env 선택과 검사 범위 확인 |
| 3 | [사이트 TLS·Keycloak CA](docs/03-tls.md), CP1 | 공용 TLS·CA ConfigMap·OIDC 연결 검사 정상 |
| 4 | [Keycloak client·관리자 그룹](docs/04-keycloak.md), 브라우저·CP1 | S256·groups mapper·그룹 가입·client Secret 준비 |
| 5 | [API server 인증](docs/05-apiserver.md), 모든 제어면 서버 | OIDC 인증 반영과 기존 관리자 접속 확인 |
| 6 | [배포·로그인·권한 검증](docs/06-deploy.md), CP1·브라우저 | 관리자 허용·별도 권한 없는 비관리자 거부·갱신 확인 |

API server 설정은 필수입니다. 제어면을 직접 관리하지 않는다면 해당 절차를 담당자에게 전달하고 완료 확인을 받습니다.
각 단계의 완료 기준을 통과한 뒤 다음으로 이동합니다. 새 터미널에서는 [실행 입력](docs/01-setup.md#2-대상-context와-실행-입력)을 다시 준비합니다.

## 운영·참고

| 하려는 일 | 문서 |
| --- | --- |
| 변수 의미·외부 env·검사 범위 | [환경설정](docs/02-environment.md) |
| Secret·CA 갱신, 장애 진단·복구 | [운영 안내](docs/07-operations.md) |
| namespace 초기화 후 다시 설치 | [재설치 전제](docs/07-operations.md#초기화-후-재설치) → 위 설치 순서 |

## 로그인과 권한

```text
Headlamp → Keycloak etch → 사내 IdP oidc → Keycloak ID Token
         → Kubernetes API server 인증 → 그룹별 RBAC
```

운영을 허용한 사람만 Keycloak 최상위 `headlamp-admins` 그룹에 가입시킵니다.
이 그룹은 Kubernetes의 `headlamp:/headlamp-admins`로 전달되고 `cluster-admin` 권한에 연결됩니다.
따라서 모든 namespace의 조회·수정·삭제, Secret 접근, RBAC 관리가 가능합니다.

다른 RBAC 권한이 있으면 함께 합산됩니다. Headlamp Pod 자체에는 사용자 조회·관리 권한을 주지 않습니다.
Portal client나 SDWT 업무 그룹은 Headlamp의 client·관리자 그룹을 대신하지 않습니다.
