# Headlamp 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

Keycloak 로그인으로 Kubernetes를 관리하는 화면(Headlamp)을 설치·운영하는 문서입니다. 단계 표시([조회]·[검사]·[변경]·[승인]·[사람])와 공통 규칙은 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | Keycloak로 로그인한 사용자의 그룹을 Kubernetes RBAC에 연결하는 관리 화면 |
| namespace | `headlamp` (Helm release `headlamp`) |
| 공개 주소 | `https://headlamp.etch.samsungds.net` (Keycloak 로그인, client `headlamp`, 관리자 그룹 `/headlamp-admins`) |
| 배포 명령 | `make ops-deploy APP=headlamp` = `headlamp-oidc-setup` → `headlamp-check` → `headlamp-up` → `headlamp-smoke` → 대조 |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, 관리자 그룹 권한 확인 `yes` |
| 먼저 필요한 것 | Keycloak 운영, 공용 TLS(`headlamp.etch.samsungds.net`), chart 파일, 사내 CA 묶음, 제어면 API server OIDC |

## 구성

- 로그인: Headlamp가 Keycloak `etch` realm의 전용 client `headlamp`로 로그인(Authorization Code + PKCE S256)하고 ID Token을 Kubernetes API server로 전달합니다.
- 인증: 모든 제어면의 API server가 같은 issuer·audience로 토큰을 검증합니다. 이 설정이 없으면 로그인 후에도 자원 조회가 401로 실패합니다.
- 권한: 토큰의 그룹 `/headlamp-admins`는 API server에서 `headlamp:/headlamp-admins`가 되고 ClusterRoleBinding `server-headlamp-admin`으로 `cluster-admin` 권한을 받습니다. 그룹 밖 사용자는 로그인해도 자원에 접근할 수 없고, Headlamp Pod의 ServiceAccount에는 조회·관리 권한을 주지 않습니다.
- 접속: 공용 Traefik(`etch-sso/traefik`)의 HTTPS entrypoint로 들어오며 경로는 `/`입니다. `headlamp` namespace 감시는 `headlamp-up`이 추가합니다.
- 배포: 저장소에 고정한 Helm chart `0.45.0`과 `helm/values.yaml`, env로 설치합니다. replica는 1입니다.

실제 주소·배치는 [서비스 접속 주소](../shared/docs/infrastructure/services.md#서비스-접속-주소)와 [앱별 배치와 스토리지 선언](../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에서 관리합니다.

## 사람이 하는 일

클러스터 밖 작업입니다. 오른쪽 명령으로 완료 여부를 먼저 확인하고, 미완료일 때만 요청합니다.

| 일 | 완료 확인 |
| --- | --- |
| 사내 미러에서 chart를 받을 수 없을 때 chart 파일 반입([방법](docs/01-prepare.md#chart와-이미지)) | `make ops-preflight APP=headlamp PROFILE=prod KUBE_CONTEXT="<context>"`가 chart를 통과 |
| 사내 Root·Issuing CA 파일을 `deploy/shared/certs/ca/`에 배치([방법](docs/01-prepare.md#tlsca-준비)) | `make ca-bundle CA_HOST=sso.etch.samsungds.net` |
| 인증서 파일 배치, DNS `headlamp.etch.samsungds.net` → APP VIP | `ls -l deploy/shared/certs/etch.samsungds.net/fullchain.crt`, `getent hosts headlamp.etch.samsungds.net` |
| 모든 제어면의 API server OIDC 설정(제어면 서버에서 수행, [계약](docs/02-authentication.md#api-server-인증)) | `kubectl --context "<context>" -n kube-system get pods -l component=kube-apiserver -o jsonpath='{.items[*].spec.containers[0].command}' \| tr ',' '\n' \| grep -c -- '--oidc-issuer-url'`가 제어면 수와 같음 |
| 관리자로 쓸 Keycloak username 결정 | 사용자가 `HEADLAMP_ADMINS` 값을 전달. 없으면 그룹만 만들고 진행 |
| 선택: 브라우저 로그인 확인(관리자 계정·그룹 밖 계정, [방법](docs/03-deploy.md#실제-사용자-로그인)) | 사용자 보고 |

Keycloak client 등록, `headlamp-admins` 그룹 생성, client secret과 CA ConfigMap 등록은 `headlamp-oidc-setup`이 합니다. 기존 client 설정은 바꾸지 않습니다.

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `HEADLAMP_ENV` | Headlamp env 경로 | `deploy/headlamp/env/k8s.env` |
| `HEADLAMP_ADMINS` | `headlamp-admins`에 가입시킬 Keycloak username(쉼표 구분) | 비움 |
| `HEADLAMP_OIDC_CA_FILE` | Keycloak CA 묶음 | `deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem` |
| `KEYCLOAK_ENV` | client 등록에 쓰는 Keycloak 관리자 계정의 출처 | `deploy/keycloak/env/prod.env` |

env 파일 키의 의미·형식과 그 밖의 실행 입력은 [환경설정](docs/01-prepare.md#환경설정)에 있습니다.

## A. 최초 설치

1. [조회] Keycloak·Traefik 확인
   ```bash
   kubectl --context "<context>" -n etch-sso get deployment keycloak traefik
   ```
   성공: 두 Deployment READY가 같은 숫자.
2. [검사] 위 표의 확인 명령으로 chart·CA 묶음·인증서 파일을 확인합니다. chart가 없으면 [변경] `make headlamp-fetch-chart`를 실행합니다. 그래도 없는 것이 있으면 멈추고 요청합니다.
3. [변경] 공용 TLS 등록: `headlamp.etch.samsungds.net`을 사이트 폴더 `etch.samsungds.net`으로 [공용 TLS 등록](../README.md#공용-tls-등록)합니다.
4. [검사] OIDC 연결 검사
   ```bash
   make headlamp-oidc-check HEADLAMP_OIDC_CA_FILE="$PWD/deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem"
   ```
   성공: `OIDC 연결 검사 통과`. 실패하면 Keycloak 주소의 DNS·방화벽·CA·issuer 문제이므로 멈춥니다.
5. [변경] 배포. Keycloak client·그룹, namespace·client secret·CA ConfigMap, Helm 설치를 수행합니다. 관리자 username을 받았다면 `HEADLAMP_ADMINS`를 붙입니다.
   ```bash
   make ops-deploy APP=headlamp KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`.
6. [조회] [C. 배포 후 확인](#c-배포-후-확인)

API server OIDC가 아직 설정되지 않았어도 배포는 진행합니다. 이 경우 로그인 후 401이 나오므로 제어면 설정을 요청하고 그 사실을 보고합니다.

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| env·chart·이미지 | [변경] `make ops-deploy APP=headlamp KUBE_CONTEXT="<context>"` |
| 관리자 추가 | [변경] `make headlamp-oidc-setup KUBE_CONTEXT="<context>" HEADLAMP_ADMINS=<username>` |
| client secret·CA 갱신 | [변경] `make headlamp-oidc-setup KUBE_CONTEXT="<context>"` 뒤 아래 재시작 블록 |
| 사이트 인증서 | A-3 |
| Keycloak CA 변경 | 멈추고 사람에게 묻기(모든 API server CA도 갱신 필요) |

[변경] 재시작. 설정이 같으면 `headlamp-up`만으로는 Pod가 다시 만들어지지 않습니다.

```bash
kubectl --context "<context>" -n headlamp rollout restart deployment/headlamp
kubectl --context "<context>" -n headlamp rollout status deployment/headlamp --timeout=180s
```

관리자 제거, 지표 미표시, 재설치 같은 그 밖의 작업은 [운영 참고](docs/04-operations.md)에 있습니다.

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context "<context>" -n headlamp get deployment,pods,ingress
kubectl --context "<context>" auth can-i list nodes --as=headlamp:rbac-probe --as-group=headlamp:/headlamp-admins --as-group=system:authenticated
kubectl --context "<context>" auth can-i list nodes --as=headlamp:rbac-outsider --as-group=system:authenticated
make headlamp-smoke KUBE_CONTEXT="<context>"
```

성공: Deployment `1/1`, 첫 `auth can-i`는 `yes`, 두 번째는 `no`, `smoke 통과: headlamp`.

## 문제 해결과 멈춤 조건

Pod·이벤트·로그는 [장애 조회](../README.md#장애-조회)의 명령에 namespace `headlamp`를 넣어 조회합니다.

| 증상 | 원인과 조치 |
| --- | --- |
| `headlamp-up`의 OIDC Secret·CA·TLS 사전 검사 실패 | `headlamp-oidc-setup` 결과와 [공용 TLS 등록](../README.md#공용-tls-등록)의 host를 확인. Secret에는 `OIDC_CLIENT_SECRET` 키 하나, ConfigMap에는 `ca.crt`가 있어야 함 |
| `ImagePullBackOff` | env의 `HEADLAMP_REGISTRY` 경로, [이미지 인증 Secret](docs/01-prepare.md#이미지-인증-secret), 노드의 registry CA 신뢰 |
| 대기 시간 초과·Pod 반복 재시작 | 이벤트·로그 조회. 시간 초과를 성공으로 보지 않음 |
| Helm은 성공했으나 Traefik 연결 실패 | 표시된 권한·controller 오류를 확인한 뒤 [변경] `make headlamp-up KUBE_CONTEXT="<context>"` 재실행 |
| 로그인·권한·HTTPS 증상 | [장애 확인](docs/04-operations.md#장애-확인)의 표 |

멈추고 사람에게 묻는 조건입니다.

- chart SHA-256 불일치, OIDC 검사 실패
- `headlamp-oidc-setup`이 관리자 접속 실패 또는 지정한 사용자를 찾지 못함
- 로그인 후 401(API server OIDC) 또는 403(그룹·mapper)
- `cannot impersonate` 오류
- client secret Regenerate, replica 증가, `helm rollback`이 필요해 보이는 경우. 실행하지 않습니다.

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [설치 준비](docs/01-prepare.md) | 준비물과 실행 위치, 환경설정(env 키·실행 입력·명령), chart와 이미지, 이미지 인증 Secret, TLS·CA 준비 |
| [로그인과 API server 인증](docs/02-authentication.md) | `headlamp-oidc-setup`의 동작, Keycloak 관리자 화면의 수동 등록·대조, 관리자 그룹, API server OIDC 계약 |
| [배포 동작과 로그인 검증](docs/03-deploy.md) | 배포 도구의 동작, 실제 HTTPS 확인, RBAC 확인, 브라우저 로그인, 설치 완료 기준 |
| [운영 참고](docs/04-operations.md) | 변경 종류별 반영, 장애 확인, 재시작과 복구, 초기화 후 재설치 |
