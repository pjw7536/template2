# Headlamp 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

Keycloak 로그인으로 Kubernetes를 관리하는 화면(Headlamp)을 설치·운영하는 문서입니다. 단계 표시([조회]·[검사]·[변경]·[승인])와 공통 규칙은 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | Keycloak로 로그인한 사용자의 그룹을 Kubernetes RBAC에 연결하는 관리 화면 |
| namespace | `headlamp` (Helm release `headlamp`) |
| 공개 주소 | `https://headlamp.etch.samsungds.net` (Keycloak 로그인, client `headlamp`, 관리자 그룹 `/headlamp-admins`) |
| 배포 명령 | `make ops-deploy APP=headlamp` = 준비 검사 → `headlamp-check` → `headlamp-oidc-setup` → `headlamp-up` → `headlamp-smoke` → 대조 |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, 관리자 그룹 권한 확인 `yes` |
| 먼저 필요한 것 | 공용 Traefik(ingress), Keycloak(`etch` realm 설정 완료), 공용 TLS(`headlamp.etch.samsungds.net`), chart 파일, 사내 CA 묶음, 제어면 API server OIDC |

## 구성

- 로그인: Headlamp가 Keycloak `etch` realm의 전용 client `headlamp`로 로그인(Authorization Code + PKCE S256)하고 ID Token을 Kubernetes API server로 전달합니다.
- 인증: 모든 제어면의 API server가 같은 issuer·audience로 토큰을 검증합니다. 이 설정이 없으면 로그인 후에도 자원 조회가 401로 실패합니다.
- 권한: 토큰의 그룹 `/headlamp-admins`는 API server에서 `headlamp:/headlamp-admins`가 되고 ClusterRoleBinding `server-headlamp-admin`으로 `cluster-admin` 권한을 받습니다. 그룹 밖 사용자는 로그인해도 자원에 접근할 수 없고, Headlamp Pod의 ServiceAccount에는 조회·관리 권한을 주지 않습니다.
- 접속: 공용 Traefik(`etch-sso/traefik`)의 HTTPS entrypoint로 들어오며 경로는 `/`입니다. `headlamp` namespace 감시는 `headlamp-up`이 추가합니다.
- 배포: 저장소에 고정한 Helm chart `0.45.0`과 `helm/values.yaml`, env로 설치합니다. replica는 1입니다.
- Keycloak 등록: client 등록, `headlamp-admins` 그룹 생성, client secret Secret과 CA ConfigMap 등록은 `headlamp-oidc-setup`이 Keycloak 관리 API로 합니다. 이미 있는 client의 설정은 바꾸지 않습니다.

실제 주소·배치는 [서비스 접속 주소](../shared/docs/infrastructure/services.md#서비스-접속-주소)와 [앱별 배치와 스토리지 선언](../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에서 관리합니다.

## 사전 준비

완료 여부를 확인하고 미완료면 준비 작업을 수행합니다. chart 받기, CA 묶음 만들기, 공용 TLS 등록은 필요한 파일이 있으면 `make ops-deploy`의 준비 검사가 자동으로 실행합니다.

| 준비 작업 | 완료 확인 |
| --- | --- |
| [공용 Traefik(ingress)](../shared/ingress/README.md)과 [Keycloak](../keycloak/README.md) 배포 | `make ops-preflight APP=headlamp KUBE_CONTEXT="<context>"`의 `먼저 필요한 앱 ingress`·`먼저 필요한 앱 keycloak` 줄이 `[통과]` |
| Keycloak `etch` realm 설정 완료([Keycloak 가이드](../keycloak/README.md)의 A) | `make keycloak-smoke KUBE_CONTEXT="<context>"`의 마지막 줄이 `smoke 통과: keycloak` |
| chart 파일. 배포할 때 사내 미러에서 자동으로 받습니다. 미러에서 받을 수 없을 때만 반입합니다([방법](docs/01-prepare.md#chart와-이미지)) | `make ops-preflight APP=headlamp KUBE_CONTEXT="<context>"`의 `chart` 줄이 `[통과]` 또는 `[자동 준비]` |
| 사내 Root·Issuing CA 파일을 `deploy/shared/certs/ca/`에 배치([방법](docs/01-prepare.md#tlsca-준비)). CA 묶음은 배포할 때 자동으로 만듭니다 | `make ops-preflight APP=headlamp KUBE_CONTEXT="<context>"`의 `사내 CA 묶음` 줄이 `[통과]` 또는 `[자동 준비]` |
| `headlamp.etch.samsungds.net`을 SAN에 가진 `fullchain.crt`·`private.key`를 `deploy/shared/certs/<사이트>/`에 배치(현재 사이트 폴더 `etch.samsungds.net`). 공용 TLS 등록은 배포할 때 자동으로 합니다 | `make ops-preflight APP=headlamp KUBE_CONTEXT="<context>"`의 `공용 TLS headlamp.etch.samsungds.net` 줄이 `[통과]` 또는 `[자동 준비]` |
| DNS `headlamp.etch.samsungds.net` → APP VIP 등록([DNS](../shared/docs/infrastructure/access.md#dns)). 없어도 배포는 진행합니다 | `getent hosts headlamp.etch.samsungds.net` |
| 모든 제어면의 API server OIDC 설정. API server가 다시 시작되므로 [승인]입니다([A. 최초 설치](#a-최초-설치) 2단계) | `kubectl --context "<context>" -n kube-system get pods -l component=kube-apiserver -o jsonpath='{range .items[*]}{.spec.nodeName}{" "}{.spec.containers[0].command}{"\n"}{end}'`가 제어면마다 한 줄을 출력하고 모든 줄에 `--oidc-issuer-url=`(`--authentication-config` 방식의 클러스터는 `--authentication-config=`)이 있음 |

`HEADLAMP_ADMINS`(관리자로 가입시킬 Keycloak username)는 요청에 주어지는 선택 입력입니다. 요청에 없으면 붙이지 않고 배포합니다. 이때 `headlamp-admins` 그룹은 구성원 없이 만들어지고, 관리자는 나중에 [B. 업데이트](#b-업데이트)의 `관리자 추가`로 가입시킵니다.

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `HEADLAMP_ENV` | Headlamp env 경로 | `deploy/headlamp/env/k8s.env`. 저장소 밖 env를 쓰면 모든 명령에 같은 값을 붙임([운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일)) |
| `HEADLAMP_ADMINS` | `headlamp-admins`에 가입시킬 Keycloak username(쉼표 구분). 요청에 주어지는 선택 입력 | 비움. 비우면 그룹만 만들고 구성원은 넣지 않음 |
| `HEADLAMP_OIDC_CA_FILE` | Keycloak CA 묶음 | `deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem` |
| `KEYCLOAK_ENV` | client 등록에 쓰는 Keycloak 관리자 계정의 출처 | `deploy/keycloak/env/prod.env` |

env 파일 키의 의미·형식과 그 밖의 실행 입력은 [환경설정](docs/01-prepare.md#환경설정)에 있습니다.

## A. 최초 설치

1. [변경] 배포. 준비 검사(chart 받기·CA 묶음·공용 TLS 등록 포함) → env·chart 검사 → Keycloak client·관리자 그룹과 namespace·client secret·CA ConfigMap 등록 → Helm 설치 → smoke → 대조를 순서대로 수행합니다. 요청에 관리자 username이 있으면 같은 명령 뒤에 `HEADLAMP_ADMINS=<username1,username2>`를 붙입니다.
   ```bash
   make ops-deploy APP=headlamp KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`. 출력에 `Headlamp OIDC 준비 완료`와 `접속 주소: https://headlamp.etch.samsungds.net/`가 있습니다.
   DNS가 아직 없으면 smoke가 APP VIP로 확인해 `smoke 통과: headlamp (DNS 미등록 host 1개)`로 끝나고 JSON의 `pending`에 DNS 등록이 남습니다. [DNS](../shared/docs/infrastructure/access.md#dns) 절로 등록합니다.
   실패하면 JSON의 `failedStep`에 따라 조치한 뒤 같은 명령을 다시 실행합니다.
   - `preflight`: `blocked`의 `item`을 봅니다. `먼저 필요한 앱 ingress`·`먼저 필요한 앱 keycloak`이면 그 앱의 가이드로 먼저 배포합니다. `chart`면 [파일 반입](../shared/docs/infrastructure/access.md#파일-반입), `사내 CA 묶음`·`공용 TLS headlamp.etch.samsungds.net`이면 [인증서 발급](../shared/docs/infrastructure/access.md#인증서-발급) 절로 파일을 준비합니다. `앱 검사`면 `make headlamp-check KUBE_CONTEXT="<context>"`를 직접 실행해 `Headlamp 실행 실패:` 줄을 확인합니다.
   - `headlamp-check`·`headlamp-oidc-setup`·`headlamp-up`·`headlamp-smoke`: [문제 해결과 멈춤 조건](#문제-해결과-멈춤-조건)의 표에서 같은 오류 문구를 찾습니다.
2. [승인] 모든 제어면의 API server OIDC 설정. 사전 준비 표의 완료 확인에서 `--oidc-issuer-url=`이 없는 제어면이 있을 때 수행합니다. API server가 다시 시작되므로 대상 제어면, 적용할 [계약](docs/02-authentication.md#api-server-인증), 영향을 보여 주고 승인받은 뒤 [API server OIDC 인증](../shared/docs/kubernetes/oidc.md) 문서의 절차를 [노드 명령 실행](../shared/docs/infrastructure/access.md#노드-명령-실행)으로 한 번에 한 대씩 수행합니다. CA 파일은 1단계가 만든 `deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem`입니다.
   성공: 사전 준비 표의 완료 확인 명령에서 모든 줄에 `--oidc-issuer-url=`이 있고 [완료 확인](docs/02-authentication.md#2-완료-확인)의 `/readyz`가 `ok`입니다.
   이 설정이 없어도 1단계 배포와 smoke는 성공합니다. 설정 전에는 로그인 후 자원 조회가 401로 실패합니다.
3. [조회] [C. 배포 후 확인](#c-배포-후-확인)

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| env·chart·이미지 | [변경] `make ops-deploy APP=headlamp KUBE_CONTEXT="<context>"`. 성공 기준은 A-1과 같음 |
| 관리자 추가 | [변경] `make headlamp-oidc-setup KUBE_CONTEXT="<context>" HEADLAMP_ADMINS=<username>`. 성공: `관리자 그룹 가입: <username>`과 `Headlamp OIDC 준비 완료` |
| 관리자 제거 | [변경] [그룹에서 빼기](docs/02-authentication.md#3-사용할-사람을-그룹에-넣기) |
| client secret·CA 갱신 | [변경] `make headlamp-oidc-setup KUBE_CONTEXT="<context>"`(성공: `Headlamp OIDC 준비 완료`) 뒤 아래 재시작 블록 |
| 사이트 인증서 갱신 | [변경] [공용 TLS 등록](../README.md#공용-tls-등록)의 명령을 `TLS_HOST=headlamp.etch.samsungds.net`으로 실행 |
| Keycloak CA 변경 | [승인] API server가 다시 시작됩니다. [Keycloak CA 변경](docs/04-operations.md#변경-종류별-반영)의 순서로 CA 묶음, 모든 제어면, Headlamp CA를 갱신 |
| 이전 Helm revision으로 되돌리기 | [승인] [Helm 롤백](docs/04-operations.md#재시작과-복구) |

[변경] 재시작. 설정이 같으면 `headlamp-up`만으로는 Pod가 다시 만들어지지 않으므로 client secret·CA를 갱신한 뒤 실행합니다.

```bash
kubectl --context "<context>" -n headlamp rollout restart deployment/headlamp
kubectl --context "<context>" -n headlamp rollout status deployment/headlamp --timeout=180s
```

성공: `deployment "headlamp" successfully rolled out`.

지표 미표시, 재설치 같은 그 밖의 작업은 [운영 참고](docs/04-operations.md)에 있습니다.

## C. 배포 후 확인

1. [조회] 워크로드, 관리자 그룹 권한, 공개 주소를 확인합니다.
   ```bash
   kubectl --context "<context>" -n headlamp get deployment,pods,ingress
   kubectl --context "<context>" auth can-i list nodes --as=headlamp:rbac-probe --as-group=headlamp:/headlamp-admins --as-group=system:authenticated
   kubectl --context "<context>" auth can-i list nodes --as=headlamp:rbac-outsider --as-group=system:authenticated
   make headlamp-smoke KUBE_CONTEXT="<context>"
   ```
   성공: Deployment `1/1`, 첫 `auth can-i`는 `yes`, 두 번째는 `no`, 마지막 줄이 `smoke 통과: headlamp`. 뒤에 `(DNS 미등록 host 1개)`가 붙어도 통과이며 DNS 등록만 남은 것입니다.
2. [검사] 관리 호스트에서 Headlamp env의 issuer를 검증합니다. Keycloak의 TLS, discovery issuer, code flow, PKCE S256, RS256 공개키를 봅니다. 저장소 밖 env를 쓰면 `HEADLAMP_ENV=<경로>`를 붙입니다.
   ```bash
   make headlamp-oidc-check HEADLAMP_OIDC_CA_FILE="$PWD/deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem"
   ```
   성공: `OIDC 연결 검사 통과: TLS·issuer·code flow·PKCE S256·RS256 공개키`. 실패하면 [연결 검사 실패](docs/01-prepare.md#3-등록과-연결-검사)의 표를 봅니다.
3. [조회] 로그인을 확인합니다. 관리 호스트에서는 [실제 HTTPS 확인](docs/03-deploy.md#실제-https-확인)까지 확인하고, 브라우저가 필요한 [실제 사용자 로그인](docs/03-deploy.md#실제-사용자-로그인) 시나리오는 [화면 기능 확인](../shared/docs/infrastructure/access.md#화면-기능-확인) 절의 방법으로 확인합니다.

## 문제 해결과 멈춤 조건

Pod·이벤트·로그는 [장애 조회](../README.md#장애-조회)의 명령에 namespace `headlamp`를 넣어 조회합니다. 도구의 오류는 `Headlamp 실행 실패:` 뒤에 나옵니다.

| 증상 | 원인과 조치 |
| --- | --- |
| `Helm 실행 파일 준비 필요` | 관리 호스트에 Helm이 없음. [관리 호스트 준비](../shared/docs/operations/04-drift.md#관리-호스트-준비)의 도구를 설치하거나 Helm 실행 파일 경로를 `HELM_BIN=<경로>`로 지정 |
| `Helm chart 준비 필요` | chart 파일이 없음. [변경] `make headlamp-fetch-chart`(성공: `chart 준비 완료:`). 미러에서 받지 못하면 [파일 반입](../shared/docs/infrastructure/access.md#파일-반입) |
| `Headlamp chart SHA-256 불일치` | chart 파일이 고정한 것과 다름. [변경] `make headlamp-fetch-chart`로 다시 받음 |
| `알 수 없거나 중복된 env 항목입니다` 등 `headlamp-check`의 env 오류 | env 키와 형식을 [환경설정](docs/01-prepare.md#환경설정)과 대조. 다른 값이 필요하면 [운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일)의 사본을 `HEADLAMP_ENV=<경로>`로 지정 |
| `Keycloak 연결 실패. 주소·DNS·CA 묶음을 확인하세요.` | 관리 호스트에서 Keycloak 공개 주소에 닿지 않음. `make keycloak-smoke KUBE_CONTEXT="<context>"`로 Keycloak을 확인하고 C-2의 연결 검사를 실행 |
| `Keycloak POST 요청 실패 (HTTP 401)`, `관리자 토큰을 발급받지 못했습니다.` | Keycloak 관리자 계정이 `KEYCLOAK_ENV`의 값과 다름. [Keycloak 관리 API](../shared/docs/infrastructure/access.md#keycloak-관리-api) 절로 계정 위치를 확인 |
| `관리자로 지정한 Keycloak 사용자를 찾을 수 없습니다: <username>` | 그 username이 Keycloak에 없음(첫 사내 로그인 전). `HEADLAMP_ADMINS`에서 그 이름을 빼고 같은 명령을 다시 실행하고, 찾지 못한 username을 보고에 남김 |
| `OIDC CA 묶음이 없습니다` | `deploy/shared/certs/ca/`에 CA 파일이 없음. [인증서 발급](../shared/docs/infrastructure/access.md#인증서-발급) 절로 준비 |
| `headlamp-up`의 `OIDC Secret에는 비어 있지 않은 OIDC_CLIENT_SECRET 키만 등록하세요.`, `OIDC CA ConfigMap에 비어 있지 않은 ca.crt가 필요합니다.`, Secret·ConfigMap `NotFound` | [변경] `make headlamp-oidc-setup KUBE_CONTEXT="<context>"`로 Secret·ConfigMap을 다시 등록. Secret에는 `OIDC_CLIENT_SECRET` 키 하나, ConfigMap에는 `ca.crt`가 있어야 함 |
| `공용 TLS 인증서가 없습니다` | [변경] [공용 TLS 등록](../README.md#공용-tls-등록)의 명령을 `TLS_HOST=headlamp.etch.samsungds.net`으로 실행 |
| `deployments.apps "traefik" not found` | 공용 Traefik이 없음. [변경] `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"` |
| `ImagePullBackOff` | env의 `HEADLAMP_REGISTRY` 경로, [이미지 인증 Secret](docs/01-prepare.md#이미지-인증-secret), 노드의 registry CA 신뢰 |
| 대기 시간 초과·Pod 반복 재시작 | 이벤트·로그 조회. 시간 초과를 성공으로 보지 않음 |
| Helm은 성공했으나 Traefik 연결 실패, smoke 404 / 503 | 표시된 권한·controller 오류와 Pod Ready를 확인한 뒤 [변경] `make headlamp-up KUBE_CONTEXT="<context>"` 재실행(감시 namespace를 다시 연결). 성공: `접속 주소: https://headlamp.etch.samsungds.net/` |
| `auth can-i`가 `cannot impersonate` | 현재 kubeconfig가 관리자 권한이 아님. 그룹 문제로 판정하지 않고 [Kubernetes API](../shared/docs/infrastructure/access.md#kubernetes-api) 절로 kubeconfig를 확인 |
| 로그인 후 401 | API server OIDC가 일부 제어면에 없음. 사전 준비 표의 완료 확인으로 확인하고 A-2를 수행 |
| 로그인 반복·callback 실패, 403, 그 밖의 로그인·HTTPS 증상 | [장애 확인](docs/04-operations.md#장애-확인)의 표 |

다음이면 멈추고 보고합니다.

- `make headlamp-fetch-chart`로 다시 받아도 `SHA-256 불일치`인 경우. `helm/chart.lock.json`의 해시를 바꾸지 않습니다.
- `Keycloak client가 이미 있어 설정을 바꾸지 않았습니다` 뒤에 로그인이 `invalid redirect URI`·`invalid_client`로 실패하거나, `Keycloak client secret을 읽지 못했습니다`가 나오는 경우. 기존 client를 지우고 다시 만들거나 client secret을 Regenerate하지 않습니다. [등록 내용](docs/02-authentication.md#2-기존-client-대조)과 다른 항목을 보고합니다.
- API server에 다른 issuer·client의 `--oidc-*` 또는 인증 설정이 이미 있는 경우. 기존 설정을 덮어쓰지 않습니다.
- C-1의 두 번째 `auth can-i`가 `yes`인 경우(그룹 밖 사용자에게 권한이 있음). 다른 RBAC 바인딩을 지우지 않고 `headlamp:` 접두사 그룹·사용자에 연결된 바인딩을 조회해 보고합니다.
- replica를 늘리거나 `helm uninstall`·namespace 삭제가 필요해 보이는 경우. 실행하지 않습니다. 로그인 state가 Pod 안에 있어 replica는 1로 유지합니다.

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [설치 준비](docs/01-prepare.md) | 준비물과 실행 위치, 환경설정(env 키·실행 입력·명령), chart와 이미지, 이미지 인증 Secret, TLS·CA 준비와 연결 검사 실패 |
| [로그인과 API server 인증](docs/02-authentication.md) | `headlamp-oidc-setup`의 동작과 등록 내용, 기존 client 대조, 관리자 그룹, client secret 직접 등록, API server OIDC 계약 |
| [배포 동작과 로그인 검증](docs/03-deploy.md) | 배포 도구의 동작, 실제 HTTPS 확인, RBAC 확인, 브라우저 로그인, 설치 완료 기준 |
| [운영 참고](docs/04-operations.md) | 변경 종류별 반영, 장애 확인, 재시작과 Helm 롤백, 초기화 후 재설치 |
