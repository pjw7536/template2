# 인증서 서버 적용과 갱신

[인증서 안내](README.md) · [원본 준비](01-prepare.md) · [추출·검증](02-extract.md) · [서버 적용](03-apply.md)

## 2단계. 서버 적용

**[추출·검증](02-extract.md)을 마친 파일을 준비한 뒤 진행합니다.**
폴더에 파일을 넣는 것만으로 기존 서버 인증서나 Kubernetes Secret이 바뀌지는 않습니다.
아래 명령은 CP1의 저장소 루트에서 Bash로 실행합니다.

이 단계에는 대상 클러스터에 접근하도록 설정된 `kubectl`과 TLS Secret을 등록할 권한이 필요합니다.
TLS Secret은 Kubernetes가 사용할 인증서와 개인키를 저장하는 리소스입니다.

### 2-1. 적용할 사이트와 대상 클러스터 선택

다음 두 블록 중 **적용할 사이트 하나만** 실행합니다. 두 사이트에 적용하려면 2단계를 각각 실행합니다.

Keycloak:

```bash
CERT_SITE=etch-sso.samsungds.net
TLS_NAMESPACE=etch-sso
TLS_SECRET=traefik-tls
```

Headlamp:

```bash
CERT_SITE=etch.samsungds.net
TLS_NAMESPACE=etch-sso
TLS_SECRET=traefik-tls
```

추출 때와 다른 터미널에서도 실행할 수 있도록 경로를 다시 설정합니다.
`kubectl config get-contexts`의 **NAME 열**에서 적용할 클러스터의 이름을 찾아 입력합니다.
context는 kubectl이 접속할 클러스터와 사용자 설정의 이름입니다.
이후 명령은 같은 터미널에서 실행합니다.

```bash
CERT_SITE_DIR="$PWD/deploy/shared/certs/$CERT_SITE"
CERT_CA_DIR="$PWD/deploy/shared/certs/ca"
set -o pipefail
kubectl config get-contexts
read -r -p '대상 context 이름: ' KUBE_CONTEXT
export KUBE_CONTEXT
```

두 도메인 모두 같은 공용 Secret을 사용합니다. 각 앱 Ingress에는 Secret 이름을 지정하지 않습니다.

등록 전에 선택한 대상과 파일 경로를 한 번 확인합니다.

```bash
printf '도메인: %s\ncontext: %s\nnamespace: %s\nSecret: %s\n' \
  "$CERT_SITE" "$KUBE_CONTEXT" "$TLS_NAMESPACE" "$TLS_SECRET"
ls -l "$CERT_SITE_DIR/fullchain.crt" "$CERT_SITE_DIR/private.key"
```

**확인할 결과:** 적용하려는 도메인·클러스터·Secret과 결과 파일 2개가 표시됩니다.
다른 대상이 표시되면 2-1에서 해당 값을 다시 설정합니다. 맞으면 2-2로 진행합니다.

### 2-2. Kubernetes TLS Secret에 등록 또는 갱신

**적용할 사이트가 [새 파일 검증](02-extract.md#1-3-pfx에서-서버-인증서개인키-추출-검증-후-저장) 또는 [기존 파일 검증](02-extract.md#1-4-이미-추출한-파일-검증--추출을-생략했다면-실행)에 성공한 뒤에만 실행합니다.**
공용 등록 도구는 도메인·만료·개인키를 검사하고 다른 도메인의 인증서를 보존합니다.

```bash
make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST="$CERT_SITE" \
  TLS_CERT_FILE="$CERT_SITE_DIR/fullchain.crt" TLS_KEY_FILE="$CERT_SITE_DIR/private.key"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

성공 시 `공용 TLS 등록 완료`가 표시됩니다. 기존 Traefik이 있으면 인증서를 다시 읽도록 재시작합니다.
앱별 인증서는 추가 등록하지 않습니다. 처음 전환하는 기존 설치는
[공용 TLS 이전 순서](../ingress/README.md#기존-설치에서-이전)를 따릅니다.
실제 HTTPS 반영은 2-4에서 확인합니다.

### 2-3. 최초 배포 시 앱 설치

**이미 서비스가 운영 중이고 인증서만 갱신했다면 이 단계는 건너뛰고 2-4로 이동합니다.**

Keycloak 배포 도구는 2-2에서 등록한 공용 SSO 인증서를 검사합니다. PEM 파일을 다시 읽지 않습니다.
Keycloak 최초 배포라면 기존 운영 env와 대상 context를 준비한 뒤 저장소 루트에서 실행합니다.

```bash
make keycloak-check KUBE_CONTEXT="$KUBE_CONTEXT"
```

검사가 성공한 뒤 다음 명령으로 배포합니다. 검사에 실패하면 오류를 해결한 뒤 다시 검사합니다.

```bash
make keycloak-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

**갱신은 2-2의 공용 등록 명령으로 수행합니다.** TLS 갱신만 하는 경우 앱 전체를 다시 배포할 필요는 없습니다.

Headlamp 최초 설치 중이라면 [03 TLS 준비](../../headlamp/03_TLS.md)로 돌아갑니다.
Headlamp 배포·접속 검사는 [06 배포와 검증](../../headlamp/06_DEPLOY_VERIFY.md)에서만 진행합니다.

### 2-4. 실제 제공되는 인증서 확인

서비스가 배포되어 있고, CP1에서 해당 도메인의 HTTPS 포트(443)에 접속할 수 있는 상태에서 실행합니다.
현재 터미널에서 선택한 사이트의 파일과 실제 서버 인증서의 SHA-256 지문을 비교합니다.
지문은 인증서를 구분하는 값으로, 두 값이 같으면 준비한 인증서가 실제로 제공되고 있다는 뜻입니다.
CA가 DER일 수도 있으므로 임시 PEM으로 변환해 검사합니다.

```bash
(
  set -euo pipefail
  cert_work=$(mktemp -d "$CERT_SITE_DIR/.live-check.XXXXXX")
  trap 'rm -rf "$cert_work"' EXIT
  if ! openssl x509 -inform PEM -in "$CERT_CA_DIR/SECDS-T2RootCA.crt" \
    -out "$cert_work/root.pem" 2>/dev/null; then
    openssl x509 -inform DER -in "$CERT_CA_DIR/SECDS-T2RootCA.crt" -out "$cert_work/root.pem"
  fi
  openssl s_client -connect "$CERT_SITE:443" -servername "$CERT_SITE" \
    -verify_hostname "$CERT_SITE" -verify_return_error -CAfile "$cert_work/root.pem" \
    -showcerts </dev/null > "$cert_work/live-chain.pem"
  openssl x509 -in "$CERT_SITE_DIR/fullchain.crt" \
    -noout -fingerprint -sha256 > "$cert_work/expected.txt"
  openssl x509 -in "$cert_work/live-chain.pem" \
    -noout -fingerprint -sha256 > "$cert_work/actual.txt"
  cmp "$cert_work/expected.txt" "$cert_work/actual.txt"
  echo 'HTTPS 체인·도메인 검증 및 서버 인증서 일치 확인 완료'
)
```

**성공 기준:** `HTTPS 체인·도메인 검증 및 서버 인증서 일치 확인 완료`가 표시됩니다.
성공 후 브라우저에서 해당 사이트를 확인합니다.
다른 사이트에도 적용하려면 2-1로 돌아가 해당 도메인을 선택하고 반복합니다.

지문이 다르면 반영 대기 여부·DNS 대상·공용 TLS 등록과 Traefik 마운트를 확인합니다.

문제가 생겨 이전 인증서로 복구해야 한다면, 앞서 보관한 유효한 인증서·개인키 쌍을
2-2의 `TLS_CERT_FILE`과 `TLS_KEY_FILE`에 지정해 다시 등록합니다. 원본 PFX 파일은 계속 보관합니다.

### 2-5. Headlamp OIDC용 CA는 별도 등록

HTTPS TLS Secret 등록과 Keycloak 로그인용 CA 등록은 별개입니다.
Headlamp에서 Keycloak 로그인을 처음 설정하거나 CA가 바뀌었다면 아래 연결 문서를 이어서 진행합니다.
CA가 그대로인 서버 인증서 갱신만 했다면 기존 OIDC용 CA 설정을 사용합니다.

[Headlamp TLS 준비](../../headlamp/03_TLS.md)의 명령으로 다음을 준비합니다.

- 입력: `ca/SECDS-T2RootCA.crt`, `ca/SECDS-T2IssuingCA.crt`
- 생성 파일: `etch-sso.samsungds.net/keycloak-ca-bundle.pem`
- Headlamp 등록: `headlamp` namespace의 `headlamp-oidc-ca` ConfigMap
- API server: 같은 CA 묶음을 각 제어면에 배치·마운트하고 OIDC 인증 설정에 연결

CA 교체 시에는 Headlamp와 각 API server의 신뢰 설정도 갱신해야 합니다.
Headlamp 재시작·로그인 확인은 [운영 참고](../../headlamp/operations/README.md#재시작과-복구)를 따릅니다.
