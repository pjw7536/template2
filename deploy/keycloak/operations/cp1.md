# CP1에서 Keycloak 배포 파일 관리

[Keycloak 시작 안내](../README.md) · [CP1 공통 Git·파일 관리](../../shared/docs/operations/cp1.md)

CP1은 배포 명령을 실행하는 호스트이며 Keycloak·PostgreSQL은 manifest에 지정한 Worker에서 실행됩니다.
저장소를 갱신하는 것과 Kubernetes·사용자 설정을 적용하는 것은 별개의 작업입니다.
최초 설치 명령은 [서버 설치](../01_SERVER_SETUP.md)와 [Keycloak 자체 설정](../04_SETUP_FLOW.md)에만 둡니다.

## 파일 소유 위치

| 내용 | 원본 위치 |
| --- | --- |
| 서버·노드·PV/PVC | `deploy/keycloak/k8s/server/` |
| 사내 IdP·프로필·mapper | `deploy/keycloak/k8s/oidc/`, `deploy/keycloak/k8s/claims/` |
| 설정 실행 | `deploy/keycloak/scripts/` |
| 등록 CSV 양식 | `deploy/keycloak/inputs/` |
| 서버·사내 IdP 설정값 | `deploy/keycloak/env/prod.env` |
| 사이트 인증서 | `deploy/shared/certs/`의 Keycloak 도메인 폴더 |
| PostgreSQL 실제 데이터 | Worker local PV 경로. Git checkout에 포함되지 않음 |

## 저장소 갱신 후 반영

[CP1 공통 안내](../../shared/docs/operations/cp1.md)에 따라 브랜치·변경사항을 확인하고 pull합니다.
그다음 변경 종류에 맞는 Keycloak 소유 안내를 사용합니다.

| 변경 내용 | 확인할 안내 |
| --- | --- |
| 문서만 변경 | 서버 적용 불필요 |
| 서버 manifest | [서버 검사·배포](../01_SERVER_SETUP.md#3-검사-후-서버-배포) |
| IdP·프로필·수신 mapper | [설정 단계와 Job 결과](../04_SETUP_FLOW.md) |
| 인증서 | [TLS 참고](../03_TLS.md), 공용 인증서 안내의 Secret 갱신 절차 |
| Portal·Headlamp client | [앱 연결](../09_APP_CONNECTIONS.md) 및 해당 앱의 소유 문서 |

DB·관리자 비밀번호는 env와 Secret만 바꾼다고 실제 서비스의 값이 바뀌지 않습니다.
설정 불일치가 발견되면 실제 값과 원본을 먼저 확인합니다.

## 외부 env 파일을 사용하는 환경

기본 입력은 저장소의 `deploy/keycloak/env/prod.env`입니다.
외부 파일을 사용하도록 구성한 서버에서는 검사와 적용에 **같은 파일 경로**를 전달합니다.
설정을 두 곳에 중복 관리하지 않습니다.

```bash
read -r -p '대상 Kubernetes context: ' KEYCLOAK_KUBE_CONTEXT
read -r -p 'Keycloak env 절대 경로: ' KEYCLOAK_ENV_PATH
make keycloak-check KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_ENV="$KEYCLOAK_ENV_PATH"
```

배포 시에도 `keycloak-up`에 같은 `KUBE_CONTEXT`, `KEYCLOAK_ENV`를 지정합니다.
사내 IdP 단계는 `keycloak-idp-setup`에 같은 경로를 전달합니다.
기본 인증서 위치와 다르면 서버 검사·배포 양쪽에 동일한 `KEYCLOAK_CERTS`를 추가합니다.

## 전달용 YAML

`rendered/`는 [Kubernetes 원본 참고](../k8s/08_KUBERNETES.md)의 별도 전달 파일입니다.
일반 설치는 단계별 Make 명령을 사용합니다.
전달 스택은 Headlamp namespace 권한·ingress 노드 라벨 등 별도 조건이 있으며,
공용 라우팅이 연결된 서버에 직접 적용하면 감시 범위·배치가 원본 값으로 바뀔 수 있습니다.
