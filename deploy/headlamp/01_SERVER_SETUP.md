# 01. 서버와 실행 입력 준비

[전체 순서](README.md) · 참고: [02 환경변수](env/02_ENVIRONMENT.md) · 다음: [03 TLS](03_TLS.md)

모든 명령은 배포 서버(CP1)의 저장소 루트에서 **같은 Bash 터미널**로 실행합니다.
각 명령이 성공했는지 확인한 뒤 다음으로 진행합니다. 새 터미널에서는 2번을 다시 실행합니다.
실행에는 `local/`이나 앱 소스가 필요하지 않습니다.

## 1. 준비할 것

| 준비 항목 | 확인 내용 |
| --- | --- |
| 도구 | Python 3.10+, Helm 3, kubectl, OpenSSL, curl, Bash, Make |
| 클러스터 | 관리자 kubeconfig, namespace·Secret·RBAC·Deployment 생성/변경 권한 |
| Keycloak | `etch` realm의 Account Console에서 `oidc` 사내 로그인 성공 |
| 사용자 | EPID 기본 username과 `loginid`를 확인하고 Identity provider links에 `oidc` 연결 완료 |
| 기존 Ingress | `etch-sso/traefik`의 HTTPS 진입점 `websecure`와 ingressClass `traefik` 사용 |
| DNS·네트워크 | Headlamp host는 기존 Traefik의 HTTPS 진입 주소로 연결. 브라우저·Headlamp Pod·모든 API server에서 Keycloak 공개 URL 접근 가능 |
| 인증서 | Headlamp fullchain·개인키, 사내 루트·중간 CA. 추출 전 원본만 있다면 다음 03에서 변환 |
| API server 담당자 | 05의 OIDC 설정을 모든 제어면에 반영할 수 있어야 함 |

Keycloak 준비가 안 됐다면 [Keycloak 자체 설정 완료 확인](../keycloak/04_SETUP_FLOW.md#설정-완료-확인)을 먼저 마칩니다.
기존 realm을 재생성하거나 Portal용 등록 명령을 실행하지 않습니다.

서버 선택 checkout이 필요하면 [서버 checkout 안내](../SERVER_CHECKOUT.md)에 따라
`bash deploy/shared/scripts/checkout-server.sh headlamp`를 사용합니다. Keycloak이 이미 실행 중이어야 합니다.

## 2. 대상 context와 실행 입력

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

```bash
test -n "$KUBE_CONTEXT" && kubectl --context "$KUBE_CONTEXT" -n etch-sso get deployment keycloak traefik
kubectl --context "$KUBE_CONTEXT" get ingressclass traefik
```

`context`는 명령을 보낼 클러스터의 이름입니다. 위 조회가 실패하면 대상과 권한부터 확인합니다.

아래 기본 파일 또는 직접 관리하는 env 경로를 선택한 뒤 [02 변수 설명](env/02_ENVIRONMENT.md)을 보며 편집합니다.
기존 env를 예시로 덮어쓰지 않습니다.

```bash
export HEADLAMP_ENV="$PWD/deploy/headlamp/env/k8s.env"
vi "$HEADLAMP_ENV"
```

이후 명령에 사용할 공개 설정을 **같은 env에서 검증해 읽습니다**. 출력은 비밀값이 없는 `이름=값` 목록입니다.
파일을 shell 코드로 실행하지 않으므로 `source`·`eval`은 사용하지 않습니다.

```bash
if HEADLAMP_SETUP_VALUES=$(make -s headlamp-setup-env); then
  while IFS='=' read -r headlamp_name headlamp_value; do
    export "$headlamp_name=$headlamp_value"
  done <<< "$HEADLAMP_SETUP_VALUES"
  unset HEADLAMP_SETUP_VALUES headlamp_name headlamp_value
  export HEADLAMP_CERT_DIR="$PWD/deploy/shared/certs/$HEADLAMP_HOST"
  export HEADLAMP_CA_DIR="$PWD/deploy/shared/certs/ca"
  export HEADLAMP_OIDC_CA_FILE=
  if [ -n "$HEADLAMP_OIDC_CA_CONFIGMAP" ]; then
    export HEADLAMP_OIDC_CA_FILE="$PWD/deploy/shared/certs/$HEADLAMP_SSO_HOST/keycloak-ca-bundle.pem"
  fi
  printf '접속 주소: https://%s/headlamp/\nCallback: %s\nIssuer: %s\n' \
    "$HEADLAMP_HOST" "$HEADLAMP_CALLBACK_URL" "$HEADLAMP_OIDC_ISSUER_URL"
else
  echo '입력 검증 실패: env를 수정한 뒤 이 블록을 다시 실행하세요. 다음 단계로 진행하지 마세요.' >&2
fi
```

실패하면 이전 변수로 진행하지 않습니다. env를 변경할 때마다 이 블록을 다시 실행합니다.
Issuer는 Keycloak의 `keycloak-public-url` + `/realms/etch`이며 사내 AD FS 주소가 아닙니다.
Callback은 이후 Keycloak client 등록 화면에 그대로 입력합니다.

## 3. 고정 chart 준비

```bash
make headlamp-fetch-chart
```

이미 `helm/vendor/headlamp-0.45.0.tgz`가 있으면 다운로드는 생략합니다.
미러를 사용할 수 없으면 [공식 0.45.0 chart](https://github.com/kubernetes-sigs/headlamp/releases/download/headlamp-helm-0.45.0/headlamp-0.45.0.tgz)를
해당 경로로 반입하거나 `export HEADLAMP_CHART_FILE=/절대경로/headlamp-0.45.0.tgz`로 지정합니다.
검사·배포는 자동 다운로드하지 않고 `helm/chart.lock.json`의 SHA-256으로 확인합니다.

```bash
make headlamp-check
```

이 명령은 선택한 `HEADLAMP_ENV`와 chart를 검사합니다. 실제 클러스터에는 적용하지 않습니다.
이미지는 `HEADLAMP_REGISTRY/headlamp-k8s/headlamp:v0.45.0`이며 노드에서 내려받을 수 있어야 합니다.

## 4. namespace와 이미지 인증 준비

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

**완료 기준:** 대상 context·입력 변수·namespace·chart 검사·필요한 이미지 인증을 준비했습니다.
다음 [03 TLS](03_TLS.md)로 진행합니다. 이 단계에서는 아직 Headlamp를 배포하지 않습니다.
