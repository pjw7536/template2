# Headlamp 설치 준비

[앱 안내](../README.md) · 다음: [Keycloak client와 API server 인증](02-authentication.md)

- [서버·실행 입력](#서버실행-입력)
- [환경설정](#환경설정)
- [TLS·CA 준비](#tlsca-준비)

## 서버·실행 입력

**목적:** 대상 클러스터·사이트 주소를 정하고 chart와 `headlamp` namespace를 준비합니다. 이 단계에서는 Headlamp 화면이 열리지 않는 것이 정상입니다.
**실행 위치:** 배포 서버(CP1)의 저장소 루트, 같은 Bash 터미널. 새 터미널을 열면 [2. 대상 context와 실행 입력](#2-대상-context와-실행-입력)을 다시 실행합니다.

| 실행 위치 | 하는 일 |
| --- | --- |
| CP1 Bash 터미널 | 저장소 루트에서 `make`·`kubectl` 실행, 인증서와 Secret 등록 |
| PC 웹 브라우저 | Keycloak 관리자 화면의 client·그룹 확인, 마지막 Headlamp 로그인 |
| 각 제어면 서버 터미널 | API server OIDC 설정. [API server 인증](02-authentication.md#api-server-인증)에서만 사용 |

`kubectl --context`를 바꿔도 SSH 접속 대상은 바뀌지 않으므로 실행 위치를 구분합니다.

### 1. 준비할 것

| 준비 항목 | 확인 내용 |
| --- | --- |
| 도구 | Python 3.10+, Helm 3, kubectl, OpenSSL, curl, Bash, Make |
| 클러스터 | 관리자 kubeconfig, namespace·Secret·RBAC·Deployment 생성/변경 권한 |
| Keycloak | [Keycloak 설정 완료 확인](../../keycloak/docs/03-configure.md#설정-완료-확인), `etch` realm의 Account Console에서 `oidc` 사내 로그인 성공 |
| 사용자 | EPID 기본 username과 `loginid`, Identity provider links의 `oidc` 연결 |
| 기존 Ingress | `etch-sso/traefik`의 HTTPS 진입점 `websecure`와 ingressClass `traefik` |
| DNS·네트워크 | Headlamp host가 Traefik HTTPS 진입 주소를 가리킴. 브라우저·Headlamp Pod·모든 API server에서 Keycloak 공개 URL 접근 가능 |
| 인증서 | Headlamp fullchain·개인키, 사내 루트·중간 CA |
| API server 담당자 | [API server 인증](02-authentication.md#api-server-인증)의 계약을 모든 제어면에 반영 가능 |

Keycloak realm을 재생성하거나 Portal용 등록 명령을 실행하지 않습니다.

### 2. 대상 context와 실행 입력

```bash
python3 --version
helm version --short
kubectl version --client
openssl version
curl --version
kubectl config get-contexts
read -r -p 'Headlamp를 설치할 context: ' KUBE_CONTEXT
export KUBE_CONTEXT
test -n "$KUBE_CONTEXT" && kubectl --context "$KUBE_CONTEXT" -n etch-sso get deployment keycloak traefik
kubectl --context "$KUBE_CONTEXT" get ingressclass traefik
```

context는 `get-contexts`의 NAME 열 값을 별표 없이 입력합니다.
**기대 결과:** `keycloak`·`traefik` Deployment의 READY 두 숫자가 같고(예: `1/1`, Traefik은 배치에 따라 `2/2`) `traefik` IngressClass가 조회됩니다.
**실패 확인:** `command not found`는 도구 설치, 목록 없음·권한 오류는 관리자 kubeconfig를 확인합니다.

기본 env를 [환경설정](#환경설정)의 표를 보며 편집합니다. 다른 파일을 쓰면 그 경로를 지정하고 기존 env를 예시로 덮어쓰지 않습니다.

```bash
export HEADLAMP_ENV="$PWD/deploy/headlamp/env/k8s.env"
vi "$HEADLAMP_ENV"
```

이후 명령에 쓸 공개 설정을 **같은 env에서 검증해 읽습니다.** 출력은 비밀값 없는 `이름=값` 목록이며, 파일을 shell 코드로 실행하지 않으므로 `source`·`eval`을 쓰지 않습니다.
env를 바꿀 때마다 이 블록을 다시 실행합니다.

```bash
if HEADLAMP_SETUP_VALUES=$(make -s headlamp-setup-env); then
  while IFS='=' read -r headlamp_name headlamp_value; do
    export "$headlamp_name=$headlamp_value"
  done <<< "$HEADLAMP_SETUP_VALUES"
  unset HEADLAMP_SETUP_VALUES headlamp_name headlamp_value
  export HEADLAMP_CERT_DIR="$PWD/deploy/shared/certs/etch.samsungds.net"
  export HEADLAMP_CA_DIR="$PWD/deploy/shared/certs/ca"
  export HEADLAMP_OIDC_CA_FILE=
  if [ -n "$HEADLAMP_OIDC_CA_CONFIGMAP" ]; then
    export HEADLAMP_OIDC_CA_FILE="$PWD/deploy/shared/certs/$HEADLAMP_SSO_HOST/keycloak-ca-bundle.pem"
  fi
  printf '접속 주소: https://%s/\nCallback: %s\nIssuer: %s\n' \
    "$HEADLAMP_HOST" "$HEADLAMP_CALLBACK_URL" "$HEADLAMP_OIDC_ISSUER_URL"
else
  echo '입력 검증 실패: env를 수정한 뒤 이 블록을 다시 실행하세요. 다음 단계로 진행하지 마세요.' >&2
fi
```

**기대 결과:** `접속 주소`(`https://headlamp.etch.samsungds.net/`), `Callback`(`…/oidc-callback`), `Issuer` 세 줄. Callback은 Keycloak client 등록에 그대로 사용합니다.
**실패 확인:** `입력 검증 실패`가 나오면 이전 변수로 진행하지 말고 env를 고친 뒤 블록 전체를 다시 실행합니다.
인증서를 다른 위치에 보관한다면 이 블록 후 `HEADLAMP_CERT_DIR`·`HEADLAMP_CA_DIR`·`HEADLAMP_OIDC_CA_FILE`을 실제 경로로 지정합니다.

### 3. 고정 chart 준비

`deploy/headlamp/helm/vendor/headlamp-0.45.0.tgz`가 이미 있으면 다운로드를 생략합니다.

```bash
make headlamp-fetch-chart
make headlamp-check
```

**기대 결과:** `chart 준비 완료:`와 파일 경로, 이어서 `서버 원본 검사 통과: headlamp/prod`. 검사는 선택한 `HEADLAMP_ENV`와 chart를 렌더할 뿐 클러스터에 적용하지 않습니다.
**실패 확인:** 미러를 쓸 수 없으면 [공식 0.45.0 chart](https://github.com/kubernetes-sigs/headlamp/releases/download/headlamp-helm-0.45.0/headlamp-0.45.0.tgz)를 같은 경로로 반입하거나
`export HEADLAMP_CHART_FILE=/절대경로/headlamp-0.45.0.tgz`로 지정합니다. `SHA-256 불일치`이면 반입한 chart를 확인하며 lock 파일의 해시를 바꾸지 않습니다.
이미지는 `HEADLAMP_REGISTRY/headlamp-k8s/headlamp:v0.45.0`이며 노드에서 내려받을 수 있어야 합니다.

### 4. namespace와 이미지 인증 준비

```bash
set -o pipefail
kubectl --context "$KUBE_CONTEXT" create namespace headlamp --dry-run=client -o yaml |
  kubectl --context "$KUBE_CONTEXT" apply -f -
```

`IMAGE_PULL_SECRET`이 비어 있으면 아래 등록을 생략합니다. 값이 있으면 registry 담당자가 제공한 해당 registry용 Docker 인증 JSON 파일을 등록합니다.
이미 올바른 Secret이 있으면 재등록하지 않으며 노드의 registry CA 신뢰는 별도로 필요합니다.

```bash
if [ -n "$IMAGE_PULL_SECRET" ]; then
  read -r -p 'Registry 인증 JSON 파일의 절대 경로: ' HEADLAMP_REGISTRY_AUTH_FILE
  kubectl --context "$KUBE_CONTEXT" -n headlamp create secret generic "$IMAGE_PULL_SECRET" \
    --type=kubernetes.io/dockerconfigjson \
    --from-file=.dockerconfigjson="$HEADLAMP_REGISTRY_AUTH_FILE" --dry-run=client -o yaml |
    kubectl --context "$KUBE_CONTEXT" apply -f -
fi
kubectl --context "$KUBE_CONTEXT" get namespace headlamp
if [ -n "$IMAGE_PULL_SECRET" ]; then
  kubectl --context "$KUBE_CONTEXT" -n headlamp get secret "$IMAGE_PULL_SECRET"
fi
```

**기대 결과:** namespace STATUS `Active`(`Terminating`이면 이전 삭제가 끝나지 않은 상태), 이미지 인증 Secret TYPE `kubernetes.io/dockerconfigjson`.
**다음 단계:** [TLS·CA 준비](#tlsca-준비).

## 환경설정

검사·배포·client JSON 생성은 모두 `env/k8s.env`(또는 `HEADLAMP_ENV`)를 읽습니다. 일반 설정과 Kubernetes 리소스 이름만 넣고 Git으로 전달합니다.
`=` 오른쪽만 바꾸며 `export`·따옴표·변수 치환을 넣지 않습니다. 알 수 없는 키(예: client secret 값)를 추가하면 검사에서 거부합니다.
Headlamp는 Keycloak env를 자동으로 읽지 않으므로 Keycloak 주소가 바뀌면 이 값도 함께 맞춥니다.

| 변수 | 현재 값 | 의미 |
| --- | --- | --- |
| `HEADLAMP_REGISTRY` | `repository.samsungds.net/proxy-docker-ghcr.io` | 노드가 이미지를 받을 ghcr.io 미러. `https://` 제외 |
| `IMAGE_PULL_SECRET` | 빈 값 | `headlamp` namespace의 이미지 인증 Secret 이름. 불필요하면 빈 값 |
| `HEADLAMP_HOST` | `headlamp.etch.samsungds.net` | 브라우저 접속 DNS 이름. scheme·경로 제외, Traefik HTTPS 진입 주소를 가리킴 |
| `HEADLAMP_OIDC_ISSUER_URL` | `https://sso.etch.samsungds.net/realms/etch` | Keycloak `keycloak-public-url` + `/realms/etch`. discovery issuer와 정확히 일치, 끝 `/` 제외. 사내 AD FS 주소가 아님 |
| `HEADLAMP_OIDC_CLIENT_ID` | `headlamp` | Keycloak 전용 client ID. API server audience도 같은 값 |
| `HEADLAMP_OIDC_SECRET` | `headlamp-oidc` | client secret을 담을 Kubernetes Secret의 **이름**. 비밀값이 아니며 `OIDC_CLIENT_SECRET` 키 하나만 등록 |
| `HEADLAMP_OIDC_CA_CONFIGMAP` | `headlamp-oidc-ca` | Pod가 Keycloak HTTPS를 신뢰할 CA ConfigMap 이름(`ca.crt` 키). 공인 CA이면 빈 값 |

CA ConfigMap은 Pod가 읽는 보관함이고, `HEADLAMP_OIDC_CA_FILE`은 CP1의 연결 검사·API server 등록에 쓰는 PEM 파일입니다.
`HEADLAMP_SSO_HOST`·`HEADLAMP_CALLBACK_URL`은 setup-env가 계산하는 값이며 env에 추가하지 않습니다.

다음은 env에 넣지 않고 Make 인자 또는 프로세스 환경변수로 전달합니다.

| 변수 | 용도 |
| --- | --- |
| `HEADLAMP_ENV` | 다른 일반 설정 파일 경로 |
| `KUBE_CONTEXT` | `headlamp-up`, `headlamp-ui`의 대상. 필수 |
| `HEADLAMP_CHART_FILE` | 반입한 고정 chart 경로. 같은 SHA-256 검사 |
| `HEADLAMP_OIDC_CA_FILE` | `headlamp-oidc-check`가 실행 서버에서 읽을 PEM CA 파일 |
| `HELM_BIN` | Helm 실행 파일 경로. 기본 `helm` |

| 명령 | 확인 범위 |
| --- | --- |
| `make headlamp-setup-env` | env 검증 후 안내용 공개 변수 출력. chart·클러스터 불필요 |
| `make headlamp-check` | 선택한 env·chart 해시·Helm 렌더. 클러스터 접속 없음 |
| `make server-check APP=headlamp PROFILE=prod` | 저장소 기본 env의 정적 검사 |
| `make headlamp-oidc-client` | 비밀값 없는 client JSON 출력. Keycloak에 자동 등록하지 않음 |
| `make headlamp-oidc-check HEADLAMP_OIDC_CA_FILE=/경로/ca.pem` | 실행 서버에서 Keycloak TLS·discovery·issuer·code flow·S256·RS256 공개키 검사. client secret·로그인·RBAC는 검사하지 않음 |
| `make headlamp-up KUBE_CONTEXT=대상` | OIDC Secret·CA 키·공용 TLS·Traefik 사전 검사 후 Helm 적용 |
| `make headlamp-ui KUBE_CONTEXT=대상` | 배포 상태와 접속 주소 확인 |

고정 계약: namespace·Helm release는 `headlamp`, baseURL은 루트 경로, 관리 그룹은 `/headlamp-admins`, Ingress는 기존 `etch-sso/traefik`입니다. env로 바꾸는 항목이 아닙니다.
`helm/values.yaml`은 보안 설정·서비스·관리자 RBAC의 원본이며, 직접 설치하면 env의 OIDC·Ingress 설정이 빠지므로 루트 Make 명령으로 적용합니다.
`HEADLAMP_OIDC_CLIENT_ID`를 바꾸면 Keycloak client와 API server audience도 함께 맞춥니다.

## TLS·CA 준비

**목적:** 사이트 인증서는 공용 Traefik(`etch-sso/traefik-tls`)에, Keycloak을 신뢰할 CA는 `headlamp` namespace에 등록합니다.
**실행 위치:** [서버·실행 입력](#서버실행-입력)의 CP1 터미널과 변수. 새 터미널이면 [실행 입력](#2-대상-context와-실행-입력)을 먼저 실행합니다.
아래는 현재 사내 루트·중간 CA 기준입니다. 다른 인증기관이나 공인 CA라면 **실행 전에** [다른 인증기관인 경우](#공개-ca-또는-다른-인증기관인-경우)를 확인합니다.

| 구성 | 용도 | 적용 위치 |
| --- | --- | --- |
| Headlamp fullchain·개인키 | 브라우저에 Headlamp 사이트 증명 | `etch-sso` namespace의 공용 Secret |
| Keycloak CA 묶음 | Headlamp가 Keycloak HTTPS 신뢰 | `headlamp` namespace의 ConfigMap |
| 같은 Keycloak CA 묶음 | API server가 Keycloak 토큰 서명키 조회 | [API server 인증](02-authentication.md#api-server-인증)에서 모든 API server에 등록 |

### 1. 필요한 파일 준비

```bash
printf '사이트 도메인: %s\n사이트 인증서 폴더: %s\nCA 원본 폴더: %s\nKeycloak CA 묶음: %s\n' \
  "$HEADLAMP_HOST" "$HEADLAMP_CERT_DIR" "$HEADLAMP_CA_DIR" "$HEADLAMP_OIDC_CA_FILE"
mkdir -p "$HEADLAMP_CERT_DIR" "$(dirname "$HEADLAMP_OIDC_CA_FILE")" "$HEADLAMP_CA_DIR"
```

출력이 비어 있으면 실행 입력을 다시 수행합니다. 공인 CA 분기에서는 `HEADLAMP_OIDC_CA_FILE`이 빈 값인 것이 정상입니다.
다음 파일을 **CP1의 위 경로**에 둡니다. 인증서·개인키 파일은 Git으로 전송되지 않으며 Keycloak 서버의 개인키는 필요 없습니다.

| 파일 | 준비 방법 |
| --- | --- |
| `$HEADLAMP_CERT_DIR/fullchain.crt` | 서버 인증서가 먼저, 중간 CA가 뒤에 있는 PEM. SAN에 Headlamp 도메인 포함, 루트 CA 제외 |
| `$HEADLAMP_CERT_DIR/private.key` | 서버 인증서와 짝인 암호화되지 않은 PEM 개인키. 소유자만 읽기 |
| `$HEADLAMP_CA_DIR/SECDS-T2RootCA.crt` | 사내 루트 CA. PEM 또는 DER |
| `$HEADLAMP_CA_DIR/SECDS-T2IssuingCA.crt` | 사내 중간 CA. PEM 또는 DER |

PFX·P7B 원본만 있으면 [인증서 추출](../../shared/docs/certificates/extract.md#1-작업할-사이트-선택)에서 사이트 선택과 추출까지만 수행하고,
이미 추출한 파일은 [기존 파일 검증](../../shared/docs/certificates/extract.md#4-이미-추출한-파일-검증--추출을-생략했다면-실행)으로 도메인·체인·개인키 짝을 확인한 뒤 돌아옵니다.
사이트 도메인과 context는 이 문서에서 정한 값과 같아야 합니다.

**기대 결과:** `ls -l`로 네 파일이 모두 조회되고 사이트 인증서 검증을 통과했습니다.

### 2. Keycloak CA 묶음 생성

원본을 보존하면서 PEM CA 묶음을 만듭니다.

```bash
(
  set -euo pipefail
  umask 077
  work=$(mktemp -d)
  trap 'rm -rf "$work"' EXIT
  for ca_name in SECDS-T2RootCA SECDS-T2IssuingCA; do
    if ! openssl x509 -inform PEM -in "$HEADLAMP_CA_DIR/$ca_name.crt" \
      -out "$work/$ca_name.pem" 2>/dev/null; then
      openssl x509 -inform DER -in "$HEADLAMP_CA_DIR/$ca_name.crt" -out "$work/$ca_name.pem"
    fi
  done
  cat "$work/SECDS-T2RootCA.pem" "$work/SECDS-T2IssuingCA.pem" > "$work/ca.pem"
  install -m 0644 "$work/ca.pem" "$HEADLAMP_OIDC_CA_FILE"
  echo 'CA 묶음 생성 완료'
)
openssl crl2pkcs7 -nocrl -certfile "$HEADLAMP_OIDC_CA_FILE" | openssl pkcs7 -print_certs -noout
```

**기대 결과:** `CA 묶음 생성 완료`와 루트·중간 CA 두 개의 subject. 같은 파일을 Airflow OIDC CA와 API server에도 사용할 수 있습니다.

### 3. 공용 TLS와 OIDC CA 등록

```bash
(
  set -euo pipefail
  make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST="$HEADLAMP_HOST" \
    TLS_CERT_FILE="$HEADLAMP_CERT_DIR/fullchain.crt" TLS_KEY_FILE="$HEADLAMP_CERT_DIR/private.key"
  make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"
  test -n "$HEADLAMP_OIDC_CA_CONFIGMAP"
  kubectl --context "$KUBE_CONTEXT" -n headlamp create configmap "$HEADLAMP_OIDC_CA_CONFIGMAP" \
    --from-file=ca.crt="$HEADLAMP_OIDC_CA_FILE" --dry-run=client -o yaml |
    kubectl --context "$KUBE_CONTEXT" apply -f -
)
kubectl --context "$KUBE_CONTEXT" -n etch-sso get secret traefik-tls
kubectl --context "$KUBE_CONTEXT" -n headlamp get configmap "$HEADLAMP_OIDC_CA_CONFIGMAP"
make headlamp-oidc-check HEADLAMP_OIDC_CA_FILE="$HEADLAMP_OIDC_CA_FILE"
```

공용 등록 도구의 동작은 [공용 TLS 등록](../../shared/docs/certificates/apply.md#2-공용-tls-secret-등록갱신--cp1)을 따릅니다.
**기대 결과:** `공용 TLS 등록 완료`, ConfigMap `created`·`configured`·`unchanged`, 마지막에 `OIDC 연결 검사 통과: TLS·issuer·code flow·PKCE S256·RS256 공개키`.

| 실패 | 확인할 것 |
| --- | --- |
| Secret·ConfigMap `NotFound` | 등록 성공 여부, context, 공용 TLS는 `etch-sso`, OIDC CA는 `headlamp` namespace와 실행 입력의 이름 |
| 이름을 찾지 못함·연결 시간 초과 | CP1에서 Keycloak 도메인의 DNS·방화벽·HTTPS 접근 |
| TLS 인증서 검증 실패 | Keycloak의 실제 발급 CA가 준비한 루트·중간 CA와 같은지, 인증서 유효기간 |
| issuer 불일치 | env의 issuer가 Keycloak 공개 URL + `/realms/etch`와 정확히 같은지 |

실행 서버에서 성공해도 Pod·API server의 네트워크·CA 신뢰는 각각 준비해야 합니다. 브라우저 PC의 CA 신뢰는 [클라이언트 신뢰 안내](../../keycloak/docs/01-prepare.md#tlsca-준비)를 참고합니다.
CA가 바뀌면 실행 호스트의 CA 파일, Headlamp ConfigMap, API server의 CA를 함께 갱신하고 [재시작](04-operations.md#재시작과-복구)합니다.

**완료 기준:** TLS Secret·OIDC CA ConfigMap이 조회되고 OIDC 연결 검사가 통과합니다.
**다음 단계:** [Keycloak client와 관리자](02-authentication.md#keycloak-client와-관리자). 실제 HTTPS는 [배포·검증](03-deploy.md)에서 확인합니다.

### 공개 CA 또는 다른 인증기관인 경우

다른 CA라면 발급기관이 제공한 체인과 파일명으로 2번을 맞추고, 두 서비스가 서로 다른 CA를 쓰면 사이트 검증용 CA와 Keycloak 신뢰용 CA를 분리합니다.
Keycloak이 공인 CA를 사용하고 기본 신뢰로 검증된다면 `HEADLAMP_OIDC_CA_CONFIGMAP`을 비우고 [실행 입력](#2-대상-context와-실행-입력)을 다시 읽습니다.
Keycloak CA 생성·ConfigMap 등록·API server의 CA 옵션은 생략하고 `make headlamp-oidc-check`를 CA 인자 없이 실행합니다. 사이트 인증서의 공용 Traefik 등록은 여전히 필요합니다.

공식 참고: [OpenSSL 인증서 검증](https://docs.openssl.org/3.0/man1/openssl-verification-options/).
