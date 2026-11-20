# Headlamp 설치 준비

[Headlamp 가이드](../README.md)

설치·업데이트 절차는 [Headlamp 가이드](../README.md)에 있습니다. 이 문서는 그 절차에 쓰는 준비물·env·chart·인증서의 상세입니다.

- [준비물과 실행 위치](#준비물과-실행-위치)
- [환경설정](#환경설정)
- [chart와 이미지](#chart와-이미지)
- [이미지 인증 Secret](#이미지-인증-secret)
- [TLS·CA 준비](#tlsca-준비)

## 준비물과 실행 위치

| 준비 항목 | 확인 내용 |
| --- | --- |
| 도구 | Python 3.10+, Helm 3, kubectl, OpenSSL, curl, Bash, Make |
| 클러스터 | 관리자 kubeconfig, namespace·Secret·RBAC·Deployment 생성/변경 권한 |
| Keycloak | [Keycloak 가이드](../../keycloak/README.md)의 설정 완료, `etch` realm의 Account Console에서 `oidc` 사내 로그인 성공 |
| 사용자 | EPID 기본 username과 `loginid`, Identity provider links의 `oidc` 연결 |
| 기존 Ingress | `etch-sso/traefik`의 HTTPS 진입점 `websecure`와 ingressClass `traefik` |
| DNS·네트워크 | Headlamp host가 Traefik HTTPS 진입 주소를 가리킴. 브라우저·Headlamp Pod·모든 API server에서 Keycloak 공개 URL 접근 가능 |
| 인증서 | Headlamp fullchain·개인키, 사내 루트·중간 CA |
| API server OIDC | [API server 인증](02-authentication.md#api-server-인증)의 계약을 모든 제어면에 반영 |

Keycloak realm을 재생성하거나 Portal용 등록 명령을 실행하지 않습니다.

| 실행 위치 | 하는 일 | 접근 방법 |
| --- | --- | --- |
| 관리 호스트의 저장소 루트 | `make`·`kubectl` 실행, Keycloak client·그룹 등록과 조회 | [Kubernetes API](../../shared/docs/infrastructure/access.md#kubernetes-api), [Keycloak 관리 API](../../shared/docs/infrastructure/access.md#keycloak-관리-api) |
| 각 제어면 | API server OIDC 설정. [API server 인증](02-authentication.md#api-server-인증)에서만 사용 | [노드 SSH](../../shared/docs/infrastructure/access.md#노드-ssh) |
| 브라우저 | Headlamp 로그인 확인 | [화면 기능 확인](../../shared/docs/infrastructure/access.md#화면-기능-확인) |

`kubectl --context`를 바꿔도 SSH 접속 대상은 바뀌지 않으므로 실행 위치를 구분합니다.

[조회] 관리 호스트의 도구와 기존 Ingress를 확인합니다.

```bash
python3 --version
helm version --short
kubectl version --client
openssl version
curl --version
kubectl --context "<context>" get ingressclass traefik
```

성공: 각 버전과 `traefik` IngressClass가 조회됩니다. `command not found`면 [관리 호스트 준비](../../shared/docs/operations/04-drift.md#관리-호스트-준비)의 도구를 설치합니다. IngressClass가 없으면 [공용 Traefik(ingress)](../../shared/ingress/README.md)을 먼저 배포하고, 권한 오류면 [Kubernetes API](../../shared/docs/infrastructure/access.md#kubernetes-api) 절로 kubeconfig를 확인합니다.

## 환경설정

검사·배포·client 등록은 모두 `env/k8s.env`(또는 `HEADLAMP_ENV`)를 읽습니다. 일반 설정과 Kubernetes 리소스 이름만 들어 있고 Git으로 전달됩니다.
값은 `=` 오른쪽에만 쓰며 `export`·따옴표·변수 치환을 넣지 않습니다. 알 수 없는 키(예: client secret 값)를 추가하면 검사에서 거부합니다.
Headlamp는 Keycloak env를 자동으로 읽지 않으므로 Keycloak 주소가 바뀌면 이 값도 함께 맞춥니다. 저장소 기본값과 다른 값이 필요하면 [운영 입력 파일](../../shared/docs/infrastructure/access.md#운영-입력-파일)의 위치에 사본을 두고 그 경로를 모든 명령에 `HEADLAMP_ENV=<경로>`로 지정합니다. 저장소의 env를 고치지 않습니다.

| 변수 | 현재 값 | 의미 |
| --- | --- | --- |
| `HEADLAMP_REGISTRY` | `repository.samsungds.net/proxy-docker-ghcr.io` | 노드가 이미지를 받을 ghcr.io 미러. `https://` 제외 |
| `IMAGE_PULL_SECRET` | 빈 값 | `headlamp` namespace의 이미지 인증 Secret 이름. 불필요하면 빈 값 |
| `HEADLAMP_HOST` | `headlamp.etch.samsungds.net` | 브라우저 접속 DNS 이름. scheme·경로 제외, Traefik HTTPS 진입 주소를 가리킴 |
| `HEADLAMP_OIDC_ISSUER_URL` | `https://sso.etch.samsungds.net/realms/etch` | Keycloak `keycloak-public-url` + `/realms/etch`. discovery issuer와 정확히 일치, 끝 `/` 제외. 사내 AD FS 주소가 아님 |
| `HEADLAMP_OIDC_CLIENT_ID` | `headlamp` | Keycloak 전용 client ID. API server audience도 같은 값 |
| `HEADLAMP_OIDC_SECRET` | `headlamp-oidc` | client secret을 담을 Kubernetes Secret의 **이름**. 비밀값이 아니며 `OIDC_CLIENT_SECRET` 키 하나만 등록 |
| `HEADLAMP_OIDC_CA_CONFIGMAP` | `headlamp-oidc-ca` | Pod가 Keycloak HTTPS를 신뢰할 CA ConfigMap 이름(`ca.crt` 키). 공인 CA이면 빈 값 |

CA ConfigMap은 Pod가 읽는 보관함이고, `HEADLAMP_OIDC_CA_FILE`은 관리 호스트의 연결 검사·ConfigMap 등록·API server 전달에 쓰는 PEM 파일입니다.
`HEADLAMP_SSO_HOST`·`HEADLAMP_CALLBACK_URL`은 `headlamp-setup-env`가 계산하는 값이며 env에 추가하지 않습니다.

다음은 env에 넣지 않고 Make 인자 또는 프로세스 환경변수로 전달합니다.

| 변수 | 용도 |
| --- | --- |
| `HEADLAMP_ENV` | 다른 일반 설정 파일 경로 |
| `KUBE_CONTEXT` | `headlamp-oidc-setup`, `headlamp-up`, `headlamp-ui`의 대상. 필수 |
| `HEADLAMP_ADMINS` | `headlamp-oidc-setup`이 `headlamp-admins`에 가입시킬 Keycloak username(쉼표 구분). 요청에 주어지는 선택 입력이며 비우면 그룹만 만듦 |
| `KEYCLOAK_ENV` | `headlamp-oidc-setup`이 Keycloak 관리자 계정을 읽는 env. 기본 `deploy/keycloak/env/prod.env` |
| `HEADLAMP_CHART_FILE` | 반입한 고정 chart 경로. 같은 SHA-256 검사 |
| `HEADLAMP_OIDC_CA_FILE` | `headlamp-oidc-check`·`headlamp-oidc-setup`이 실행 서버에서 읽을 PEM CA 파일 |
| `HELM_BIN` | Helm 실행 파일 경로. 기본 `helm` |

| 명령 | 확인 범위 |
| --- | --- |
| `make headlamp-setup-env` | [조회] env 검증 후 공개 설정을 `이름=값`으로 출력(접속 host·issuer·client ID·Secret 이름·Callback). chart·클러스터 불필요 |
| `make headlamp-check KUBE_CONTEXT="<context>"` | [검사] 선택한 env·chart 해시·Helm 렌더. 클러스터에 접속하지 않지만 `KUBE_CONTEXT`는 지정해야 함. 성공: `서버 원본 검사 통과: headlamp/prod` |
| `make server-check APP=headlamp PROFILE=prod` | [검사] 저장소 기본 env의 정적 검사 |
| `make headlamp-oidc-client` | [조회] 비밀값 없는 client JSON 출력. Keycloak에 등록하지 않음 |
| `make headlamp-oidc-check HEADLAMP_OIDC_CA_FILE=/경로/ca.pem` | [검사] 실행 서버에서 Keycloak TLS·discovery·issuer·code flow·S256·RS256 공개키 검사. client secret·로그인·RBAC는 검사하지 않음 |
| `make headlamp-oidc-setup KUBE_CONTEXT="<context>"` | [변경] Keycloak client·관리자 그룹과 `headlamp` namespace·client secret Secret·CA ConfigMap 준비 |
| `make headlamp-up KUBE_CONTEXT="<context>"` | [변경] OIDC Secret·CA 키·공용 TLS·Traefik 사전 검사 후 Helm 적용 |
| `make headlamp-ui KUBE_CONTEXT="<context>"` | [조회] 배포 상태와 접속 주소 확인 |

고정 계약: namespace·Helm release는 `headlamp`, baseURL은 루트 경로, 관리 그룹은 `/headlamp-admins`, Ingress는 기존 `etch-sso/traefik`입니다. env로 바꾸는 항목이 아닙니다.
`helm/values.yaml`은 보안 설정·서비스·관리자 RBAC의 원본이며, 직접 설치하면 env의 OIDC·Ingress 설정이 빠지므로 루트 Make 명령으로 적용합니다.
`HEADLAMP_OIDC_CLIENT_ID`를 바꾸면 Keycloak client와 API server audience도 함께 맞춥니다.

## chart와 이미지

고정 chart는 `deploy/headlamp/helm/vendor/headlamp-0.45.0.tgz`입니다. `make ops-deploy APP=headlamp`의 준비 검사가 없으면 아래 명령을 자동으로 실행하므로 보통은 따로 할 일이 없습니다.

[변경] 직접 받을 때 씁니다. 사내 미러에서 내려받아 해시를 확인한 뒤 같은 경로에 둡니다. 이미 있는 파일은 같은 내용으로 다시 씁니다.

```bash
make headlamp-fetch-chart
```

성공: `chart 준비 완료:`와 파일 경로.
미러에서 받을 수 없으면 [파일 반입](../../shared/docs/infrastructure/access.md#파일-반입) 절의 방법으로 [공식 0.45.0 chart](https://github.com/kubernetes-sigs/headlamp/releases/download/headlamp-helm-0.45.0/headlamp-0.45.0.tgz)를 가져와 같은 경로에 두거나 모든 명령에 `HEADLAMP_CHART_FILE=/절대경로/headlamp-0.45.0.tgz`를 붙입니다.
`SHA-256 불일치`이면 가져온 chart가 고정한 파일과 다른 것입니다. `helm/chart.lock.json`의 해시를 바꾸지 않습니다.

이미지는 `HEADLAMP_REGISTRY/headlamp-k8s/headlamp:v0.45.0`이며 노드에서 내려받을 수 있어야 합니다.

## 이미지 인증 Secret

`IMAGE_PULL_SECRET`이 비어 있으면 필요 없습니다. 값이 있을 때만 수행하며 배포 도구는 이 Secret을 만들지 않습니다.
해당 registry용 Docker 인증 JSON 파일은 [운영 입력 파일](../../shared/docs/infrastructure/access.md#운영-입력-파일)의 위치(관리 호스트의 외부 앱 설정 폴더)에 둔 것을 씁니다. 올바른 Secret이 이미 있으면 유지하며 노드의 registry CA 신뢰는 별도로 확인합니다.

[변경] namespace가 없으면 만들고 인증 JSON 파일을 Secret으로 등록한 뒤 결과를 조회합니다.

```bash
kubectl --context "<context>" create namespace headlamp --dry-run=client -o yaml |
  kubectl --context "<context>" apply -f -
kubectl --context "<context>" -n headlamp create secret generic <IMAGE_PULL_SECRET 값> \
  --type=kubernetes.io/dockerconfigjson \
  --from-file=.dockerconfigjson=<Registry 인증 JSON 파일의 절대 경로> --dry-run=client -o yaml |
  kubectl --context "<context>" apply -f -
kubectl --context "<context>" -n headlamp get secret <IMAGE_PULL_SECRET 값>
```

성공: Secret TYPE이 `kubernetes.io/dockerconfigjson`입니다. namespace STATUS가 `Terminating`이면 이전 삭제가 끝나지 않은 상태입니다.

## TLS·CA 준비

사이트 인증서는 공용 Traefik(`etch-sso/traefik-tls`)에, Keycloak을 신뢰할 CA는 `headlamp` namespace에 등록합니다.
아래는 현재 사내 루트·중간 CA 기준입니다. 다른 인증기관이나 공인 CA라면 먼저 [다른 인증기관인 경우](#공개-ca-또는-다른-인증기관인-경우)를 확인합니다.

| 구성 | 용도 | 적용 위치 | 등록 |
| --- | --- | --- | --- |
| Headlamp fullchain·개인키 | 브라우저에 Headlamp 사이트 증명 | `etch-sso` namespace의 공용 Secret | `make ops-deploy APP=headlamp`의 준비 검사가 등록. 직접 등록은 [공용 TLS 등록](../../README.md#공용-tls-등록) |
| Keycloak CA 묶음 | Headlamp가 Keycloak HTTPS 신뢰 | `headlamp` namespace의 ConfigMap `headlamp-oidc-ca` | `headlamp-oidc-setup`이 등록 |
| 같은 Keycloak CA 묶음 | API server가 Keycloak 토큰 서명키 조회 | 모든 API server | [API server 인증](02-authentication.md#api-server-인증) |

### 1. 필요한 파일 준비

[변경] 다음 파일을 관리 호스트의 저장소 checkout 아래에 둡니다. 발급받은 파일을 가져오는 방법은 [인증서 발급](../../shared/docs/infrastructure/access.md#인증서-발급) 절에 있습니다. 이 작업에 Keycloak 서버의 개인키는 필요 없습니다.

| 파일 | 준비 방법 |
| --- | --- |
| `deploy/shared/certs/etch.samsungds.net/fullchain.crt` | 서버 인증서가 먼저, 중간 CA가 뒤에 있는 PEM. SAN에 Headlamp 도메인 포함, 루트 CA 제외 |
| `deploy/shared/certs/etch.samsungds.net/private.key` | 서버 인증서와 짝인 암호화되지 않은 PEM 개인키. 소유자만 읽기 |
| `deploy/shared/certs/ca/SECDS-T2RootCA.crt` | 사내 루트 CA. PEM 또는 DER |
| `deploy/shared/certs/ca/SECDS-T2IssuingCA.crt` | 사내 중간 CA. PEM 또는 DER |

PFX·P7B 원본만 있으면 [인증서 추출](../../shared/docs/certificates/extract.md#1-작업할-사이트-선택)에서 사이트 선택과 추출까지만 수행하고,
이미 추출한 파일은 [기존 파일 검증](../../shared/docs/certificates/extract.md#4-이미-추출한-파일-검증--추출을-생략했다면-실행)으로 도메인·체인·개인키 짝을 확인합니다.

[조회] 완료 확인:

```bash
ls -l deploy/shared/certs/etch.samsungds.net/fullchain.crt deploy/shared/certs/etch.samsungds.net/private.key deploy/shared/certs/ca/
```

성공: 네 파일이 모두 보입니다.

### 2. Keycloak CA 묶음 생성

`make ops-deploy APP=headlamp`의 준비 검사가 묶음이 없으면 아래 명령을 자동으로 실행합니다. CA를 교체했을 때는 직접 실행합니다.

[변경] `deploy/shared/certs/ca/`의 `.crt`·`.pem`·`.cer` 인증서(PEM·DER 모두 가능)를 이름순으로 이어 붙여 PEM 묶음을 만듭니다. 원본 파일은 바꾸지 않습니다.

```bash
make ca-bundle CA_HOST=sso.etch.samsungds.net
```

성공: `CA 묶음 준비 완료: deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem`. `CA 인증서가 없습니다`면 1번의 CA 파일을 [인증서 발급](../../shared/docs/infrastructure/access.md#인증서-발급) 절로 준비합니다.
`make ca-bundle`은 실행할 때마다 CA 폴더의 현재 파일로 묶음을 다시 만듭니다. `headlamp-oidc-setup`은 `HEADLAMP_OIDC_CA_FILE`을 지정하지 않으면 같은 경로의 묶음을 그대로 사용하고, 없을 때만 같은 방식으로 만듭니다. CA를 교체했으면 `make ca-bundle`을 다시 실행한 뒤 `headlamp-oidc-setup`으로 ConfigMap을 갱신합니다.
같은 파일을 Airflow OIDC CA와 API server에도 사용할 수 있습니다.

[조회] 묶음에 든 인증서 확인:

```bash
openssl crl2pkcs7 -nocrl -certfile deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem | openssl pkcs7 -print_certs -noout
```

성공: 루트·중간 CA 두 개의 subject가 보입니다.

### 3. 등록과 연결 검사

사이트 인증서의 공용 TLS 등록과 CA ConfigMap 등록은 [가이드 A](../README.md#a-최초-설치)의 배포 명령이 수행하고, OIDC 연결 검사는 [가이드 C](../README.md#c-배포-후-확인)에 있습니다. 공용 등록 도구의 동작은 [공용 TLS 등록](../../shared/docs/certificates/apply.md#2-공용-tls-secret-등록갱신--관리-호스트)을 따릅니다.

[조회] 등록 결과:

```bash
kubectl --context "<context>" -n etch-sso get secret traefik-tls
kubectl --context "<context>" -n headlamp get configmap headlamp-oidc-ca
```

성공: 두 리소스가 조회됩니다.

OIDC 연결 검사의 성공 문구는 `OIDC 연결 검사 통과: TLS·issuer·code flow·PKCE S256·RS256 공개키`입니다. 실패하면 다음을 확인합니다.

| 실패 | 확인할 것 |
| --- | --- |
| Secret·ConfigMap `NotFound` | 등록 성공 여부, context, 공용 TLS는 `etch-sso`, OIDC CA는 `headlamp` namespace와 env의 이름 |
| 이름을 찾지 못함·연결 시간 초과 | 관리 호스트에서 Keycloak 도메인까지의 경로. [DNS](../../shared/docs/infrastructure/access.md#dns)와 [방화벽](../../shared/docs/infrastructure/access.md#방화벽) 절의 `찾는 방법`으로 확인 |
| TLS 인증서 검증 실패 | Keycloak의 실제 발급 CA가 준비한 루트·중간 CA와 같은지, 인증서 유효기간 |
| issuer 불일치 | env의 issuer가 Keycloak 공개 URL + `/realms/etch`와 정확히 같은지 |
| `사내 CA 설정에는 HEADLAMP_OIDC_CA_FILE로 로컬 CA 묶음을 지정하세요` | `HEADLAMP_OIDC_CA_CONFIGMAP`이 있는 env에서 `HEADLAMP_OIDC_CA_FILE` 없이 검사함 |

실행 서버에서 성공해도 Pod·API server의 네트워크·CA 신뢰는 각각 준비해야 합니다. 브라우저 PC의 CA 신뢰는 [클라이언트 PC 신뢰 등록](../../shared/docs/certificates/apply.md#클라이언트-pc-신뢰-등록)을 참고합니다.
CA가 바뀌면 관리 호스트의 CA 파일과 묶음, Headlamp ConfigMap, 모든 API server의 CA를 함께 갱신하고 [재시작](04-operations.md#재시작과-복구)합니다. 순서는 [Keycloak CA 변경](04-operations.md#변경-종류별-반영)에 있습니다.

### 공개 CA 또는 다른 인증기관인 경우

다른 CA라면 발급기관이 제공한 체인으로 2번의 묶음을 맞추고(CA 폴더의 파일을 바꾸거나 PEM 묶음을 `HEADLAMP_OIDC_CA_FILE`로 지정), 두 서비스가 서로 다른 CA를 쓰면 사이트 검증용 CA와 Keycloak 신뢰용 CA를 분리합니다.
Keycloak이 공인 CA를 사용하고 기본 신뢰로 검증된다면 env의 `HEADLAMP_OIDC_CA_CONFIGMAP`을 비웁니다.
이 경우 CA 묶음 생성·ConfigMap 등록·API server의 CA 옵션은 생략하고 `make headlamp-oidc-check`를 CA 인자 없이 실행합니다. 사이트 인증서의 공용 Traefik 등록은 여전히 필요합니다.

공식 참고: [OpenSSL 인증서 검증](https://docs.openssl.org/3.0/man1/openssl-verification-options/).
