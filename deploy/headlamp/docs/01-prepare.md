# Headlamp 설치 준비

[앱 안내](../README.md)

- [서버·실행 입력](#서버실행-입력)
- [환경설정](#환경설정)
- [TLS·CA 준비](#tlsca-준비)

## 서버·실행 입력

배포 서버(CP1)의 저장소 루트에서 같은 Bash 터미널을 사용합니다.
명령 하나가 성공한 것을 확인한 뒤 다음 명령을 실행합니다.
새 터미널을 열면 2번의 실행 입력을 다시 준비합니다. `local/`이나 앱 소스는 필요하지 않습니다.

**이 단계의 목표:** 사용할 클러스터와 사이트 주소를 정하고, 설치 파일과 `headlamp` namespace를 준비합니다.
아직 Headlamp 화면이 열리지 않는 것이 정상입니다.

먼저 CP1에 SSH로 접속한 뒤 이 저장소가 있는 디렉터리로 이동합니다.
아래 `/실제/저장소/경로`를 서버의 경로로 바꿉니다. 이후 명령은 이 디렉터리에서 실행합니다.

```bash
cd /실제/저장소/경로
pwd
ls Makefile deploy/headlamp/README.md
```

두 파일 이름이 출력되면 작업 위치가 맞습니다. `No such file`이면 저장소 위치부터 확인하세요.
Keycloak의 realm·사내 IdP를 다시 만드는 단계는 수행하지 않습니다.

### 실행 위치와 입력 읽는 법

작업할 곳은 세 군데입니다.

| 작업할 곳 | 여기서 하는 일 |
| --- | --- |
| CP1의 Bash 터미널 | 저장소 루트에서 `make`·`kubectl` 실행, 인증서와 Secret 등록 |
| PC의 웹 브라우저 | Keycloak 관리자 화면에서 client·그룹 등록, 마지막에 Headlamp 로그인 |
| 각 제어면 서버의 터미널 | Kubernetes API server가 Keycloak 토큰을 받아들이도록 설정. API server 인증 단계에서만 사용 |

`kubectl --context ...`는 선택한 클러스터에 명령을 보냅니다.
`sudo vi /etc/kubernetes/...`는 현재 SSH로 접속한 서버의 파일을 편집합니다.
context를 바꿔도 SSH 접속 대상은 바뀌지 않으므로 실행 위치를 구분합니다.

### 1. 준비할 것

| 준비 항목 | 확인 내용 |
| --- | --- |
| 도구 | Python 3.10+, Helm 3, kubectl, OpenSSL, curl, Bash, Make |
| 클러스터 | 관리자 kubeconfig, namespace·Secret·RBAC·Deployment 생성/변경 권한 |
| Keycloak | `etch` realm의 Account Console에서 `oidc` 사내 로그인 성공 |
| 사용자 | EPID 기본 username과 `loginid`를 확인하고 Identity provider links에 `oidc` 연결 완료 |
| 기존 Ingress | `etch-sso/traefik`의 HTTPS 진입점 `websecure`와 ingressClass `traefik` 사용 |
| DNS·네트워크 | Headlamp host는 기존 Traefik의 HTTPS 진입 주소로 연결. 브라우저·Headlamp Pod·모든 API server에서 Keycloak 공개 URL 접근 가능 |
| 인증서 | Headlamp fullchain·개인키, 사내 루트·중간 CA. 추출 전 원본만 있다면 [TLS 준비](#tlsca-준비)에서 변환 |
| API server 담당자 | [API server 인증](02-authentication.md#api-server-인증)의 OIDC 설정을 모든 제어면에 반영할 수 있어야 함 |

Keycloak 준비가 안 됐다면 [Keycloak 자체 설정 완료 확인](../../keycloak/docs/03-configure.md#설정-완료-확인)을 먼저 마칩니다.
기존 realm을 재생성하거나 Portal용 등록 명령을 실행하지 않습니다.

서버 선택 checkout이 필요하면 [서버 checkout 안내](../../shared/docs/operations/01-checkout.md#선택-checkout)에 따라
`bash deploy/shared/scripts/checkout-server.sh headlamp`를 사용합니다. Keycloak이 이미 실행 중이어야 합니다.

### 2. 대상 context와 실행 입력

```bash
ls Makefile
python3 --version
helm version --short
kubectl version --client
openssl version
curl --version
kubectl config get-contexts
read -r -p 'Headlamp를 설치할 context: ' KUBE_CONTEXT
export KUBE_CONTEXT
```

`kubectl config get-contexts` 결과의 NAME 열에서 설치할 클러스터를 고릅니다.
별표(`*`)나 서버 IP를 빼고 context 이름 자체를 입력합니다.

목록이 없거나 권한 오류가 나면 관리자 kubeconfig부터 준비합니다.
`command not found`가 나온 도구는 설치한 뒤 다시 확인합니다.

```bash
test -n "$KUBE_CONTEXT" && kubectl --context "$KUBE_CONTEXT" -n etch-sso get deployment keycloak traefik
kubectl --context "$KUBE_CONTEXT" get ingressclass traefik
```

`context`는 명령을 보낼 클러스터의 이름입니다. 위 조회가 실패하면 대상과 권한부터 확인합니다.
정상이라면 `keycloak`, `traefik` Deployment가 조회되고 READY의 두 숫자가 같아야 합니다
(예: `1/1`, Traefik은 배치에 따라 `2/2`). `traefik` IngressClass도 조회되어야 합니다.

아래 기본 파일 또는 직접 관리하는 env 경로를 선택한 뒤 [변수 설명](#환경설정)을 보며 편집합니다.
기존 env를 예시로 덮어쓰지 않습니다.

```bash
export HEADLAMP_ENV="$PWD/deploy/headlamp/env/k8s.env"
vi "$HEADLAMP_ENV"
```

다음 항목을 먼저 확인하세요. 입력 형식·전체 목록은 [환경변수](#환경설정)에 있습니다.

| 확인할 항목 | 무엇을 입력하나요? |
| --- | --- |
| `HEADLAMP_HOST` | `headlamp.etch.samsungds.net`. DNS가 기존 Traefik HTTPS 진입 주소를 가리켜야 함 |
| `HEADLAMP_OIDC_ISSUER_URL` | 현재 정상 작동하는 Keycloak 공개 주소 뒤에 `/realms/etch`를 붙인 값. 사내 AD FS 주소가 아님 |
| `HEADLAMP_REGISTRY` | 노드에서 이미지를 받을 수 있는 registry 미러 경로. `https://` 제외 |
| `IMAGE_PULL_SECRET` | registry 인증이 필요하면 새로 등록할 Secret 이름, 필요 없으면 `=` 뒤를 비움 |
| `HEADLAMP_OIDC_CA_CONFIGMAP` | 현재 사내 CA 구성은 기본 이름 유지. Keycloak이 공인 CA라면 [TLS 준비](#tlsca-준비)의 공개 CA 분기 확인 |

처음 설치하고 별도 명명 규칙이 없다면 client ID와 TLS·OIDC Secret·CA ConfigMap **이름은 기본값을 유지**해도 됩니다.
이름을 적는 것만으로 Secret이 만들어지지는 않습니다. 서버 준비·TLS·Keycloak 설정 단계에서 각각 등록합니다.
client secret의 실제 비밀값은 이 env 파일에 넣지 않습니다.

이후 명령에 사용할 공개 설정을 **같은 env에서 검증해 읽습니다**. 출력은 비밀값이 없는 `이름=값` 목록입니다.
파일을 shell 코드로 실행하지 않으므로 `source`·`eval`은 사용하지 않습니다.

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

실패하면 이전 변수로 진행하지 않습니다. env를 변경할 때마다 이 블록을 다시 실행합니다.
Issuer는 Keycloak의 `keycloak-public-url` + `/realms/etch`이며 사내 AD FS 주소가 아닙니다.
Callback은 이후 Keycloak client 등록 화면에 그대로 입력합니다.

성공하면 `접속 주소`, `Callback`, `Issuer` 세 줄이 출력됩니다. 공개 주소이므로 작업 메모에 남겨 둡니다.

- 브라우저에서 열 주소: `https://headlamp.etch.samsungds.net/`
- Keycloak에 등록할 callback: `/oidc-callback`

`입력 검증 실패`가 나오면 env를 고친 뒤 위 if 블록 전체를 다시 실행합니다.

### 3. 고정 chart 준비

```bash
make headlamp-fetch-chart
```

chart는 Helm이 Kubernetes 리소스를 만드는 데 사용하는 설치 묶음입니다.
위 명령이 성공하면 `chart 준비 완료:`와 파일 경로가 나옵니다.
이미 `deploy/headlamp/helm/vendor/headlamp-0.45.0.tgz`가 있으면 이 명령 실행을 생략합니다.
미러를 사용할 수 없으면 [공식 0.45.0 chart](https://github.com/kubernetes-sigs/headlamp/releases/download/headlamp-helm-0.45.0/headlamp-0.45.0.tgz)를
해당 경로로 반입하거나 `export HEADLAMP_CHART_FILE=/절대경로/headlamp-0.45.0.tgz`로 지정합니다.
검사·배포는 자동 다운로드하지 않고 `helm/chart.lock.json`의 SHA-256으로 확인합니다.

```bash
make headlamp-check
```

이 명령은 선택한 `HEADLAMP_ENV`와 chart를 검사합니다. 실제 클러스터에는 적용하지 않습니다.
`서버 원본 검사 통과: headlamp/prod`가 나오면 성공입니다.
`No such file`이면 chart 경로를, `SHA-256 불일치`이면 반입한 chart 버전을 확인합니다.
해시 검사를 우회하거나 lock 파일의 해시를 임의로 바꾸지 않습니다.
이미지는 `HEADLAMP_REGISTRY/headlamp-k8s/headlamp:v0.45.0`이며 노드에서 내려받을 수 있어야 합니다.

### 4. namespace와 이미지 인증 준비

```bash
set -o pipefail
kubectl --context "$KUBE_CONTEXT" create namespace headlamp --dry-run=client -o yaml |
  kubectl --context "$KUBE_CONTEXT" apply -f -
```

`IMAGE_PULL_SECRET`이 비어 있으면 이 namespace의 이미지 인증 등록은 생략합니다.
값이 있다면 registry 담당자가 제공한 Docker 인증 JSON 파일을 다음 명령으로 등록합니다.
사용자 전체 Docker 설정이 아닌 해당 registry용 파일을 사용합니다.

```bash
if [ -n "$IMAGE_PULL_SECRET" ]; then
  read -r -p 'Registry 인증 JSON 파일의 절대 경로: ' HEADLAMP_REGISTRY_AUTH_FILE
  kubectl --context "$KUBE_CONTEXT" -n headlamp create secret generic "$IMAGE_PULL_SECRET" \
    --type=kubernetes.io/dockerconfigjson \
    --from-file=.dockerconfigjson="$HEADLAMP_REGISTRY_AUTH_FILE" --dry-run=client -o yaml |
    kubectl --context "$KUBE_CONTEXT" apply -f -
fi
```

이미 올바른 Secret이 있다면 재등록하지 않습니다. node의 registry CA 신뢰는 별도로 필요합니다.

namespace가 준비됐는지 확인합니다.

```bash
kubectl --context "$KUBE_CONTEXT" get namespace headlamp
if [ -n "$IMAGE_PULL_SECRET" ]; then
  kubectl --context "$KUBE_CONTEXT" -n headlamp get secret "$IMAGE_PULL_SECRET"
fi
```

namespace의 STATUS는 `Active`여야 합니다. 초기화 후 `Terminating`이면 삭제가 아직 끝나지 않은 상태입니다.
이미지 인증 Secret을 등록했다면 TYPE이 `kubernetes.io/dockerconfigjson`인지 확인합니다.

**완료 기준:** 대상 context·입력 변수·namespace·chart 검사·필요한 이미지 인증을 준비했습니다.
다음 [TLS](#tlsca-준비)로 진행합니다. 이 단계에서는 아직 Headlamp를 배포하지 않습니다.

## 환경설정

검사·배포·client JSON 생성은 모두 `env/k8s.env`를 읽습니다.
이 파일에는 일반 설정과 Kubernetes 리소스의 이름을 넣고 Git으로 전달합니다.
실제 client secret은 [Keycloak 설정](02-authentication.md#keycloak-client와-관리자)의 절차로 Kubernetes Secret에 등록합니다.

Headlamp가 Keycloak env를 자동으로 읽지는 않습니다.
Keycloak 주소가 바뀌면 이 문서의 관련 값도 함께 맞춥니다.

### 처음 편집할 때

[서버 준비](#서버실행-입력)에서 연 파일에서 `=` 오른쪽만 바꿉니다. `export`나 따옴표를 넣지 않고 한 줄에 한 항목을 씁니다.
아래는 이 프로젝트의 운영값입니다. namespace와 Ingress 이름은 모두 `headlamp`입니다.

```dotenv
HEADLAMP_HOST=headlamp.etch.samsungds.net
HEADLAMP_OIDC_ISSUER_URL=https://sso.etch.samsungds.net/realms/etch
HEADLAMP_OIDC_SECRET=headlamp-oidc
IMAGE_PULL_SECRET=
```

| 헷갈리기 쉬운 값 | 차이 |
| --- | --- |
| `HEADLAMP_HOST`와 issuer | 앞은 Headlamp 사이트, 뒤는 인증을 담당하는 Keycloak realm URL |
| `HEADLAMP_OIDC_CLIENT_ID`와 `HEADLAMP_OIDC_SECRET` | 앞은 Keycloak에 등록한 앱 ID, 뒤는 Kubernetes에 만들 Secret의 이름 |
| `HEADLAMP_OIDC_SECRET`와 Client secret | `headlamp-oidc`는 보관함 이름이며 비밀값이 아님. 실제 비밀값은 [Keycloak 설정](02-authentication.md#keycloak-client와-관리자)의 숨김 입력으로 등록 |
| CA ConfigMap과 CA 파일 | ConfigMap은 Pod가 읽는 보관함. 파일은 CP1 연결 검사·API server 등록에 쓰는 PEM |

env를 저장한 뒤에는 [서버 준비의 실행 입력](#2-대상-context와-실행-입력)을 다시 읽어야
현재 터미널 변수와 이후 등록 명령에도 수정값이 반영됩니다.

### env에 입력하는 값

| 변수 | 의미와 확인 위치 |
| --- | --- |
| `HEADLAMP_REGISTRY` | Headlamp 이미지 미러. `https://` 없이 입력 |
| `IMAGE_PULL_SECRET` | `headlamp` namespace의 이미지 인증 Secret. 불필요하면 빈 값 |
| `HEADLAMP_HOST` | 브라우저 접속 DNS 이름. scheme·경로 제외 |
| `HEADLAMP_OIDC_ISSUER_URL` | Keycloak의 `keycloak-public-url` + `/realms/etch`. discovery issuer와 정확히 일치, 끝 `/` 제외 |
| `HEADLAMP_OIDC_CLIENT_ID` | 전용 client ID. 기본 `headlamp`. API server audience도 동일하게 설정 |
| `HEADLAMP_OIDC_SECRET` | 같은 namespace의 Secret 이름. 비어 있지 않은 `OIDC_CLIENT_SECRET` 키 하나만 등록 |
| `HEADLAMP_OIDC_CA_CONFIGMAP` | 같은 namespace의 Keycloak CA ConfigMap 이름. PEM `ca.crt` 키 필요. 공개 CA이면 빈 값 |

`KEY=value` 형식으로 입력합니다. 값에 shell 따옴표·변수 치환을 넣지 않습니다.
`.secrets.env`를 읽지 않으며 client secret 값을 이 파일에 추가하면 검사에서 거부합니다.

### Make 명령에 전달하는 값

다음 항목은 `k8s.env`에 추가하지 않고 Make 인자 또는 프로세스 환경변수로 전달합니다.

| 변수 | 용도 |
| --- | --- |
| `HEADLAMP_ENV` | 다른 일반 설정 파일의 경로 |
| `KUBE_CONTEXT` | 배포·접속 확인 대상. `headlamp-up`, `headlamp-ui`에서 필수 |
| `HEADLAMP_CHART_FILE` | 반입한 고정 chart 경로. 동일 SHA-256 검사 적용 |
| `HEADLAMP_OIDC_CA_FILE` | `headlamp-oidc-check`가 실행 서버에서 읽을 PEM CA 파일 |
| `HELM_BIN` | Helm 실행 파일 경로. 기본 `helm` |

### 검사 범위

| 명령 | 확인하는 내용 |
| --- | --- |
| `make headlamp-setup-env` | 선택한 env 검증 후 안내 명령용 공개 변수 출력. chart·클러스터 불필요 |
| `make headlamp-check` | 선택한 `HEADLAMP_ENV`·chart 해시·Helm 렌더. 클러스터 접속 없음 |
| `make server-check APP=headlamp PROFILE=prod` | 저장소 기본 `env/k8s.env`의 정적 검사. 사용자 지정 env는 위 headlamp-check로 검사 |
| `make headlamp-oidc-client` | 현재 env에 맞는 비밀값 없는 client JSON 출력. Keycloak에 자동 등록하지 않음 |
| `make headlamp-oidc-check HEADLAMP_OIDC_CA_FILE=/경로/ca.pem` | 실행 서버에서 Keycloak TLS·discovery·issuer·code flow·S256·RS256 공개키 검사. chart·관리자 credential 불필요 |
| `make headlamp-up KUBE_CONTEXT=대상` | Secret·CA 키·TLS·Traefik 사전 검사 후 Helm 적용 |
| `make headlamp-ui KUBE_CONTEXT=대상` | 배포 상태와 접속 주소 확인 |

OIDC 연결 검사와 실제 로그인 검증은 다릅니다.
client 존재 여부, secret의 유효성, 그룹 가입, 실제 토큰 서명과 Kubernetes 권한은 별도로 확인합니다.
Headlamp Pod와 모든 API server에서도 discovery·JWKS 주소에 접근할 수 있어야 합니다.

Keycloak 인증서 갱신으로 CA가 바뀌면 세 곳을 함께 갱신합니다.
실행 호스트의 검사 파일, Headlamp ConfigMap, API server의 CA 파일입니다.
변경 후 Headlamp 재시작은 [운영 참고](04-operations.md)를 따릅니다.

### 고정 계약과 파일 역할

namespace·Helm release는 `headlamp`, baseURL은 빈 값(루트 경로), 관리 그룹은 `/headlamp-admins`입니다.
설치 명령은 기존 `etch-sso/traefik`을 사용합니다. 이 이름들은 env로 변경하는 항목이 아닙니다.
`HEADLAMP_OIDC_CLIENT_ID`를 바꾸면 Keycloak client와 API server audience도 함께 맞춥니다.

| 파일 | 역할 |
| --- | --- |
| `helm/chart.lock.json` | 고정 chart 버전·미러 URL·SHA-256 |
| `helm/values.yaml` | 보안 설정·서비스·관리자 RBAC의 기본 원본 |
| `scripts/manage.py` | env 검증·chart 렌더·Secret 검사·Helm 적용·기존 Traefik 연결 |
| `env/k8s.env` | 배포할 공개 주소·registry·Secret/CA 이름 |

`helm/values.yaml`만 직접 설치하면 env의 OIDC·Ingress 설정이 빠집니다. 루트 Make 명령으로 적용합니다.
`HEADLAMP_SSO_HOST`·`HEADLAMP_CALLBACK_URL`은 setup-env가 계산하는 값이며 입력 파일에 추가하지 않습니다.
[서버 준비](#서버실행-입력)은 로컬 인증서 경로도 현재 host 기준으로 준비합니다. 다른 위치에 보관한다면 그 단계 후
`HEADLAMP_CERT_DIR`·`HEADLAMP_CA_DIR`·`HEADLAMP_OIDC_CA_FILE`을 실제 경로로 지정합니다.

## TLS·CA 준비

[서버 준비](#서버실행-입력)에서 읽은 변수와 대상 context를 유지합니다. 새 터미널에서는 [실행 입력](#2-대상-context와-실행-입력)을 먼저 준비합니다.
아래는 현재 사내 루트·중간 CA를 사용하는 설치 절차입니다.
다른 인증기관이나 공인 CA를 쓰면 먼저 이 문서 끝의 해당 분기를 읽고 입력·생략 단계를 맞춥니다.

**실행 위치:** [서버 준비](#서버실행-입력)에서 사용하던 CP1 Bash 터미널, 저장소 루트.
**목표:** 사이트 인증서는 공용 Traefik에, Keycloak을 신뢰할 CA는 `headlamp` namespace에 등록합니다.
운영 도메인은 `headlamp.etch.samsungds.net`, 공용 인증서 저장소는 `etch-sso/traefik-tls`입니다.
Keycloak의 `sso.etch.samsungds.net` 인증서와 구분해 준비합니다.

먼저 아래에서 사용할 경로가 준비됐는지 확인합니다. 출력값이 비어 있으면 [서버 준비](#서버실행-입력)의 실행 입력부터 다시 수행하세요.
단, 공인 CA 분기에서는 `HEADLAMP_OIDC_CA_FILE`이 빈 값인 것이 정상입니다.

```bash
printf '사이트 도메인: %s\n사이트 인증서 폴더: %s\nCA 원본 폴더: %s\nKeycloak CA 묶음: %s\n' \
  "$HEADLAMP_HOST" "$HEADLAMP_CERT_DIR" "$HEADLAMP_CA_DIR" "$HEADLAMP_OIDC_CA_FILE"
```

기본 사내 CA를 사용하면 아래 1~3번을 진행합니다. Keycloak 또는 Headlamp 인증서의 발급기관이 다르면
**명령을 실행하기 전에** 끝의 [공개 CA 또는 다른 인증기관인 경우](#공개-ca-또는-다른-인증기관인-경우)를 확인합니다.

| 구성 | 용도 | 적용 위치 |
| --- | --- | --- |
| Headlamp fullchain·개인키 | 브라우저에 Headlamp 사이트 증명 | `etch-sso` namespace의 공용 Secret |
| Keycloak CA 묶음 | Headlamp가 Keycloak HTTPS 신뢰 | `headlamp` namespace의 ConfigMap |
| 같은 Keycloak CA 묶음 | Kubernetes가 Keycloak 토큰 서명키 조회 | [API server 인증](02-authentication.md#api-server-인증)에서 모든 API server에 파일·마운트 등록 |

### 1. 필요한 파일 준비

```bash
mkdir -p "$HEADLAMP_CERT_DIR" "$(dirname "$HEADLAMP_OIDC_CA_FILE")" "$HEADLAMP_CA_DIR"
```

다음 파일을 준비합니다. 인증서·개인키 파일은 Git으로 전송되지 않습니다.

| 파일 | 준비 방법 |
| --- | --- |
| `$HEADLAMP_CERT_DIR/fullchain.crt` | 서버 인증서가 먼저, 중간 CA가 뒤에 있는 PEM |
| `$HEADLAMP_CERT_DIR/private.key` | 서버 인증서와 짝인 암호화되지 않은 PEM 개인키. 소유자만 읽기 |
| `$HEADLAMP_CA_DIR/SECDS-T2RootCA.crt` | 사내 루트 CA. PEM 또는 DER |
| `$HEADLAMP_CA_DIR/SECDS-T2IssuingCA.crt` | 사내 중간 CA. PEM 또는 DER |

표의 파일이 모두 준비되어 있으면 PFX·P7B 추출은 건너뜁니다.
Keycloak 서버의 개인키는 가져오지 않아도 됩니다.

PFX 원본만 있다면 [공용 인증서 추출](../../shared/docs/certificates/extract.md#1단계-인증서-추출)에서
사이트 선택과 3번 추출까지만 수행한 뒤 이 문서로 돌아옵니다.
그 문서의 앱 배포 단계까지 진행하지는 않습니다.
사이트 도메인과 context는 [서버 준비](#서버실행-입력)에서 정한 값과 같아야 합니다. 인증서는 공용 Secret에 등록합니다.

파일은 관리자 PC가 아니라 **지금 명령을 실행하는 CP1의 위 경로**에 있어야 합니다.
인증서 담당자에게 받은 파일을 서버로 옮기고 표의 이름으로 배치한 뒤 확인합니다.

```bash
ls -l "$HEADLAMP_CERT_DIR/fullchain.crt" "$HEADLAMP_CERT_DIR/private.key" \
  "$HEADLAMP_CA_DIR/SECDS-T2RootCA.crt" "$HEADLAMP_CA_DIR/SECDS-T2IssuingCA.crt"
```

네 파일 모두 조회되어야 합니다. `No such file`이면 아직 검증 명령을 실행하지 말고 경로·파일명을 맞춥니다.
`fullchain.crt`의 SAN에 Headlamp 도메인이 포함되어 있어야 합니다. 공용 SAN 인증서를 사용하면 같은 원본을 host별로 등록할 수 있습니다.

### 2. 인증서 검증과 CA 묶음 생성

아래 블록은 기존 원본을 보존하면서 PEM CA 묶음을 만듭니다.

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
  openssl verify -purpose sslserver -verify_hostname "$HEADLAMP_HOST" \
    -CAfile "$work/SECDS-T2RootCA.pem" -untrusted "$work/SECDS-T2IssuingCA.pem" \
    "$HEADLAMP_CERT_DIR/fullchain.crt"
  openssl x509 -in "$HEADLAMP_CERT_DIR/fullchain.crt" -pubkey -noout > "$work/cert-public.pem"
  openssl pkey -in "$HEADLAMP_CERT_DIR/private.key" -passin pass: -pubout > "$work/key-public.pem"
  cmp "$work/cert-public.pem" "$work/key-public.pem"
  cat "$work/SECDS-T2RootCA.pem" "$work/SECDS-T2IssuingCA.pem" > "$work/ca.pem"
  install -m 0644 "$work/ca.pem" "$HEADLAMP_OIDC_CA_FILE"
  chmod 600 "$HEADLAMP_CERT_DIR/private.key"
  echo '사이트 인증서 검증·CA 묶음 생성 완료'
)
```

정상이면 `fullchain.crt: OK`와 완료 메시지가 나옵니다. 오류가 나면 다음 단계로 넘어가지 않습니다.

| 오류 | 의미 |
| --- | --- |
| `hostname mismatch` | 사이트 도메인과 인증서가 다름 |
| `unable to get ... issuer certificate` | CA 체인 확인 필요 |
| `cmp` 결과가 다름 | 인증서와 개인키가 서로 짝이 맞지 않음 |

위 검증은 별도 CA 파일을 사용합니다. fullchain 자체에 중간 CA가 들어 있는지도 아래 명령으로 확인합니다.

```bash
openssl crl2pkcs7 -nocrl -certfile "$HEADLAMP_CERT_DIR/fullchain.crt" |
  openssl pkcs7 -print_certs -noout
```

현재 체인에서는 Headlamp 서버 인증서와 중간 CA가 순서대로 나와야 합니다. 루트 CA는 fullchain에 넣지 않습니다.

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
```

```bash
kubectl --context "$KUBE_CONTEXT" -n etch-sso get secret traefik-tls
kubectl --context "$KUBE_CONTEXT" -n headlamp get configmap "$HEADLAMP_OIDC_CA_CONFIGMAP"
make headlamp-oidc-check HEADLAMP_OIDC_CA_FILE="$HEADLAMP_OIDC_CA_FILE"
```

등록 시 `created`, `configured` 또는 `unchanged`가 출력되면 적용된 것입니다.
마지막 명령은 `OIDC 연결 검사 통과: TLS·issuer·code flow·PKCE S256·RS256 공개키`를 출력해야 합니다.

| 여기서 실패한다면 | 확인할 것 |
| --- | --- |
| Secret·ConfigMap이 `NotFound` | 등록 명령 성공 여부, context, 공용 TLS는 `etch-sso`, OIDC CA는 `headlamp` namespace와 [서버 준비](#서버실행-입력)에서 읽은 이름 |
| 이름을 찾지 못함·연결 시간 초과 | CP1에서 Keycloak 도메인의 DNS·방화벽·HTTPS 접근 |
| TLS 인증서 검증 실패 | Keycloak의 실제 발급 CA가 준비한 루트·중간 CA와 같은지, 인증서 유효기간 |
| issuer 불일치 | env의 issuer가 Keycloak 공개 URL + `/realms/etch`와 정확히 같은지 |

접속 중인 Keycloak의 TLS 체인·issuer·code flow·S256·RS256 공개키까지 확인합니다.
실행 서버에서 성공해도 Pod·API server의 네트워크·CA 신뢰는 각각 준비해야 합니다.
검사는 실제 client secret·로그인 토큰·RBAC까지 확인하지 않습니다.
브라우저 PC의 CA 신뢰는 [클라이언트 신뢰 안내](../../keycloak/docs/01-prepare.md#tlsca-준비)를 참고합니다.

**완료 기준:** TLS Secret·OIDC CA ConfigMap이 조회되고 OIDC 연결 검사가 통과합니다.
다음 [Keycloak](02-authentication.md#keycloak-client와-관리자)으로 진행합니다. Headlamp의 실제 HTTPS 확인은 배포 후 [배포·검증](03-deploy.md)에서 합니다.

### 공개 CA 또는 다른 인증기관인 경우

위 명령은 현재 사내 CA 두 파일을 기준으로 합니다. 다른 CA라면 발급기관이 제공한 체인과 파일명으로
2번을 맞추고 두 서비스가 서로 다른 CA를 쓰면 사이트 검증용 CA와 Keycloak 신뢰용 CA를 분리합니다.
Keycloak이 공인 CA를 사용하고 클라이언트 기본 신뢰로 검증된다면 `HEADLAMP_OIDC_CA_CONFIGMAP`을 비우고
[서버 준비](#서버실행-입력)의 입력을 다시 읽습니다. Keycloak CA 생성·ConfigMap 등록·[API server 인증](02-authentication.md#api-server-인증)의 OIDC CA 파일 옵션은 생략하고
`make headlamp-oidc-check`를 CA 인자 없이 실행합니다. 사이트 인증서의 공용 Traefik 등록은 여전히 필요합니다.

공식 참고: [OpenSSL 인증서 검증](https://docs.openssl.org/3.0/man1/openssl-verification-options/).
