# 서버 인증서 보관 폴더

실제 서버에 저장소를 준비한 뒤 **사이트에 맞는 하위 폴더에 파일을 넣습니다.**
Keycloak과 Headlamp의 인증서·개인키는 도메인별로 구분하고 공용 CA는 `ca/`에 둡니다.
`.gitignore`, 이 README와 폴더 유지용 `.gitkeep`만 Git으로 관리합니다. 실제 인증서 파일은 모두 제외합니다.

처음에는 아래 순서로 읽습니다.

1. **넣을 파일 / 서버에 넣는 순서**: 사이트별 파일 배치
2. **원본에서 추출하고 서버에 적용하기**: 사이트 선택 → 추출 또는 기존 파일 검증 → TLS Secret 등록 → 실제 HTTPS 확인
3. **Headlamp OIDC용 CA는 별도 등록**: 로그인 연동에 필요한 CA 설정

## 넣을 파일

```text
deploy/shared/certs/
├── README.md
├── .gitignore
├── etch-sso.samsungds.net/       # Keycloak
│   ├── .gitkeep
│   ├── etch-sso.samsungds.net.p7b
│   ├── etch-sso.samsungds.net.pfx
│   ├── keycloak-fullchain.crt
│   ├── keycloak.key
│   └── keycloak-ca-bundle.pem   # OIDC 가이드에서 나중에 생성
├── etch.samsungds.net/           # Headlamp 접속 도메인
│   ├── .gitkeep
│   ├── etch.samsungds.net.p7b
│   ├── etch.samsungds.net.pfx
│   ├── etch-fullchain.crt
│   └── etch.key
└── ca/                          # 공용 인증기관 원본
    ├── .gitkeep
    ├── SECDS-T2IssuingCA.crt
    └── SECDS-T2RootCA.crt
```

파일 이름은 위와 같이 유지합니다. 기존에 공용 폴더 바로 아래 넣었다면 위 구조에 맞춰 이동합니다. 이미 추출한 파일이 있으므로 지금 다시 추출할 필요는 없습니다.

| 파일 | 용도 |
| --- | --- |
| `etch-sso.samsungds.net.p7b`, `etch-sso.samsungds.net.pfx` | Keycloak 인증서 발급 원본 보관 |
| `keycloak-fullchain.crt` | Keycloak HTTPS 서버 인증서와 중간 인증서 체인 |
| `keycloak.key` | Keycloak 인증서와 짝인 개인키 |
| `SECDS-T2IssuingCA.crt` | 중간 인증기관 인증서 |
| `SECDS-T2RootCA.crt` | 루트 인증기관 인증서 |
| `etch.samsungds.net.p7b`, `etch.samsungds.net.pfx` | Headlamp 접속 도메인의 인증서 발급 원본 보관 |
| `etch-fullchain.crt` | Headlamp HTTPS 서버 인증서와 중간 인증서 체인 |
| `etch.key` | Headlamp 인증서와 짝인 개인키 |

CA 파일은 나중에 Keycloak 인증서를 신뢰하기 위한 CA 묶음을 만들 때 사용합니다.
확장자만으로 PEM/DER 형식을 확정할 수 없으므로 실제 파일을 넣은 뒤 형식과 체인을 확인합니다.

## 서버에 넣는 순서

1. CP1에서 저장소 루트로 이동합니다. `Makefile`이 있는 위치입니다.
2. 아래 명령으로 보관 폴더를 준비합니다.
3. 평소 사용하는 파일 전송 도구로 사이트별 폴더에 각각 4개, `ca/`에 2개를 넣습니다.
   `keycloak-ca-bundle.pem`은 지금 넣을 파일이 아니라 [OIDC 가이드](../../headlamp/OIDC.md)에서 생성할 파일입니다.

```bash
mkdir -p deploy/shared/certs/{etch-sso.samsungds.net,etch.samsungds.net,ca}
chmod 700 deploy/shared/certs deploy/shared/certs/{etch-sso.samsungds.net,etch.samsungds.net,ca}
```

파일을 모두 넣은 뒤 개인키와 PFX의 읽기 권한을 소유자로 제한합니다.

```bash
chmod 600 deploy/shared/certs/etch-sso.samsungds.net/keycloak.key deploy/shared/certs/etch.samsungds.net/etch.key \
  deploy/shared/certs/etch-sso.samsungds.net/etch-sso.samsungds.net.pfx \
  deploy/shared/certs/etch.samsungds.net/etch.samsungds.net.pfx
```

파일은 배포 명령을 실행하는 계정이 읽을 수 있어야 합니다.
Git으로 실제 인증서가 전송되지는 않으므로 서버마다 필요한 파일은 별도로 넣습니다.

## 배포할 때 사용할 경로

Keycloak 배포 도구는 `deploy/shared/certs/etch-sso.samsungds.net`을 기본으로 사용합니다.
저장소 루트에서 아래 명령을 실행합니다.
인증서 배치가 끝나고 기존 운영 env와 대상 context가 준비됐을 때 실행합니다.

```bash
make keycloak-check KUBE_CONTEXT="$KUBE_CONTEXT"
make keycloak-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

Headlamp TLS 등록 시 사용할 파일 경로는 다음과 같습니다.

```text
인증서: deploy/shared/certs/etch.samsungds.net/etch-fullchain.crt
개인키: deploy/shared/certs/etch.samsungds.net/etch.key
```

**폴더에 파일을 넣는 것만으로 기존 서버 인증서나 Kubernetes Secret이 바뀌지는 않습니다.**
파일 배치 후 아래의 **원본에서 추출하고 서버에 적용하기** 절차로 검증·등록합니다.

관련 안내: [Keycloak 인증서](../../keycloak/TLS.md),
[Headlamp HTTPS](../../headlamp/HTTPS_CERTIFICATE_GUIDE.md),
[Headlamp Keycloak 로그인](../../headlamp/OIDC.md).
기존 안내의 인증서 파일 경로를 사용할 때는 이 공용 폴더의 경로로 바꿉니다.

## 원본에서 추출하고 서버에 적용하기

아래 명령은 **CP1의 저장소 루트에서 Bash로 실행**합니다.
이미 추출한 fullchain과 개인키가 정상이라면 추출은 생략하고 검증·적용부터 진행합니다.
PFX 비밀번호는 명령이 물어볼 때 입력합니다.

### 1. 작업할 사이트 선택

다음 두 블록 중 **작업할 사이트 하나만** 실행합니다. 다른 사이트는 이 절차를 마친 뒤 다시 선택합니다.

Keycloak 인증서를 작업할 때:

```bash
CERT_SITE=etch-sso.samsungds.net
CERT_PREFIX=keycloak
TLS_NAMESPACE=etch-sso
TLS_SECRET=keycloak-tls
```

Headlamp 인증서를 작업할 때:

```bash
CERT_SITE=etch.samsungds.net
CERT_PREFIX=etch
TLS_NAMESPACE=headlamp
TLS_SECRET=headlamp-tls
```

그다음 공통 경로와 대상 클러스터를 설정합니다. 이후 명령은 같은 터미널에서 실행합니다.

```bash
CERT_SITE_DIR="$PWD/deploy/shared/certs/$CERT_SITE"
CERT_CA_DIR="$PWD/deploy/shared/certs/ca"
set -o pipefail
kubectl config get-contexts
read -r -p '대상 context 이름: ' KUBE_CONTEXT
export KUBE_CONTEXT
```

Secret 이름은 현재 프로젝트 기본값입니다. 운영 중인 Ingress가 다른 Secret을 참조한다면
실제 이름에 맞춰 `TLS_SECRET`을 바꾸고, Headlamp의 `HEADLAMP_TLS_SECRET`도 일치시킵니다.

### 2. P7B에서 공개 인증서 묶음 확인 — 필요한 경우

P7B에는 개인키가 없습니다. 서버 인증서·CA가 어떤 순서로 들어 있는지 확인할 때 사용합니다.
아래 명령은 PEM으로 먼저 읽고, 실패하면 DER로 다시 읽습니다.

```bash
(
  set -euo pipefail
  if ! openssl pkcs7 -inform PEM -in "$CERT_SITE_DIR/$CERT_SITE.p7b" \
    -print_certs -out "$CERT_SITE_DIR/p7b-certificates.pem" 2>/dev/null; then
    openssl pkcs7 -inform DER -in "$CERT_SITE_DIR/$CERT_SITE.p7b" \
      -print_certs -out "$CERT_SITE_DIR/p7b-certificates.pem"
  fi
  openssl crl2pkcs7 -nocrl -certfile "$CERT_SITE_DIR/p7b-certificates.pem" |
    openssl pkcs7 -print_certs -noout
)
```

`subject`와 `issuer`가 표시됩니다. P7B의 나열 순서가 서버→중간→루트 순서라는 보장은 없습니다.
이 묶음을 그대로 fullchain으로 사용하지 않습니다. 현재는 `ca/`에 제공받은 개별 CA 두 파일이 있으므로
다음 단계에서 이 파일들로 체인을 검증합니다.

PFX에 들어 있는 CA만 별도로 확인하려면 다음 명령을 사용합니다.
CA가 포함되지 않은 PFX라면 결과에 인증서가 없을 수 있습니다.

```bash
openssl pkcs12 -in "$CERT_SITE_DIR/$CERT_SITE.pfx" \
  -cacerts -nokeys -out "$CERT_SITE_DIR/pfx-ca-certificates.pem"
```

### 3. PFX에서 서버 인증서·개인키 추출, 검증 후 저장

아래 블록은 PFX 비밀번호를 두 번 물어봅니다. 인증서와 개인키를 각각 꺼내기 때문입니다.
임시 폴더에서 추출·검증한 뒤에만 정식 파일로 저장합니다.
기존 파일은 해당 사이트의 `backups/` 아래에 보관합니다.

```bash
(
  set -euo pipefail
  umask 077
  cert_work=$(mktemp -d "$CERT_SITE_DIR/.extract.XXXXXX")
  trap 'rm -rf "$cert_work"' EXIT

  # CA 원본은 유지하고 PEM 형식으로 읽습니다.
  for ca_name in SECDS-T2RootCA SECDS-T2IssuingCA; do
    if ! openssl x509 -inform PEM -in "$CERT_CA_DIR/$ca_name.crt" \
      -out "$cert_work/$ca_name.pem" 2>/dev/null; then
      openssl x509 -inform DER -in "$CERT_CA_DIR/$ca_name.crt" \
        -out "$cert_work/$ca_name.pem"
    fi
  done

  openssl pkcs12 -in "$CERT_SITE_DIR/$CERT_SITE.pfx" -clcerts -nokeys |
    openssl x509 -out "$cert_work/leaf.crt"
  openssl pkcs12 -in "$CERT_SITE_DIR/$CERT_SITE.pfx" -nocerts -nodes |
    openssl pkey -out "$cert_work/private.key"

  # 도메인·기간·CA 체인과 인증서/개인키의 짝을 검사합니다.
  openssl verify -purpose sslserver -verify_hostname "$CERT_SITE" \
    -CAfile "$cert_work/SECDS-T2RootCA.pem" \
    -untrusted "$cert_work/SECDS-T2IssuingCA.pem" "$cert_work/leaf.crt"
  openssl x509 -in "$cert_work/leaf.crt" -pubkey -noout > "$cert_work/cert-public.pem"
  openssl pkey -in "$cert_work/private.key" -pubout > "$cert_work/key-public.pem"
  cmp "$cert_work/cert-public.pem" "$cert_work/key-public.pem"

  # 서버 인증서 다음에 중간 CA를 붙입니다. 루트 CA는 fullchain에 넣지 않습니다.
  cat "$cert_work/leaf.crt" "$cert_work/SECDS-T2IssuingCA.pem" > "$cert_work/fullchain.crt"
  mkdir -p "$CERT_SITE_DIR/backups"
  cert_backup=$(mktemp -d "$CERT_SITE_DIR/backups/before-extract.XXXXXX")
  for cert_name in "$CERT_PREFIX-fullchain.crt" "$CERT_PREFIX.key"; do
    if [ -f "$CERT_SITE_DIR/$cert_name" ]; then
      cp -p "$CERT_SITE_DIR/$cert_name" "$cert_backup/"
    fi
  done
  install -m 0600 "$cert_work/private.key" "$CERT_SITE_DIR/$CERT_PREFIX.key"
  install -m 0644 "$cert_work/fullchain.crt" "$CERT_SITE_DIR/$CERT_PREFIX-fullchain.crt"
  printf '추출·검증 완료. 기존 파일 보관 위치: %s\n' "$cert_backup"
)
```

**성공 기준:** `leaf.crt: OK`와 `추출·검증 완료`가 표시됩니다.
`cmp`는 두 공개키가 같으면 아무 출력 없이 성공합니다. 오류가 나면 등록 단계로 넘어가지 않습니다.

OpenSSL 3에서 구형 PFX 암호의 `unsupported` 오류가 발생한 경우에만
위의 해당 `openssl pkcs12` 명령에 `-legacy`를 추가해 다시 실행합니다.
비밀번호 오류나 체인 오류에는 이 옵션을 사용하지 않습니다.
이 절차는 PFX에 서버 인증서·개인키 한 쌍이 있고 제공된 중간 CA 하나로 체인이 연결되는 경우를 기준으로 합니다.

### 4. 이미 추출한 파일 검증 — 추출을 생략했다면 실행

위 3번을 통과했다면 이 검사는 반복하지 않아도 됩니다.

```bash
(
  set -euo pipefail
  cert_work=$(mktemp -d "$CERT_SITE_DIR/.verify.XXXXXX")
  trap 'rm -rf "$cert_work"' EXIT
  for ca_name in SECDS-T2RootCA SECDS-T2IssuingCA; do
    if ! openssl x509 -inform PEM -in "$CERT_CA_DIR/$ca_name.crt" \
      -out "$cert_work/$ca_name.pem" 2>/dev/null; then
      openssl x509 -inform DER -in "$CERT_CA_DIR/$ca_name.crt" \
        -out "$cert_work/$ca_name.pem"
    fi
  done
  openssl verify -purpose sslserver -verify_hostname "$CERT_SITE" \
    -CAfile "$cert_work/SECDS-T2RootCA.pem" \
    -untrusted "$cert_work/SECDS-T2IssuingCA.pem" \
    "$CERT_SITE_DIR/$CERT_PREFIX-fullchain.crt"
  openssl x509 -in "$CERT_SITE_DIR/$CERT_PREFIX-fullchain.crt" -pubkey -noout > "$cert_work/cert-public.pem"
  openssl pkey -in "$CERT_SITE_DIR/$CERT_PREFIX.key" -passin pass: -pubout > "$cert_work/key-public.pem"
  cmp "$cert_work/cert-public.pem" "$cert_work/key-public.pem"
  echo '인증서 체인·도메인·기간·개인키 일치 확인 완료'
)
```

fullchain은 **서버 인증서가 첫 번째, 이어서 중간 CA** 순서여야 합니다.
위 검증은 별도의 CA 파일로 체인을 확인하므로 fullchain에 중간 CA가 실제로 포함돼 있는지도 확인합니다.

```bash
openssl crl2pkcs7 -nocrl -certfile "$CERT_SITE_DIR/$CERT_PREFIX-fullchain.crt" |
  openssl pkcs7 -print_certs -noout
```

현재 구성은 서버 인증서와 `SECDS-T2IssuingCA` 두 개가 순서대로 나와야 합니다.

### 5. Kubernetes TLS Secret에 등록 또는 갱신

**3번 또는 4번 검증에 성공한 뒤에만 실행합니다.**
아래 명령은 1번에서 선택한 사이트의 TLS Secret을 실제로 생성하거나 갱신합니다.
폴더에 파일을 넣는 것과 달리, 이 단계부터 서버에 반영됩니다.

```bash
(
  set -euo pipefail
  test -n "$KUBE_CONTEXT"
  kubectl --context "$KUBE_CONTEXT" create namespace "$TLS_NAMESPACE" --dry-run=client -o yaml |
    kubectl --context "$KUBE_CONTEXT" apply -f -
  kubectl --context "$KUBE_CONTEXT" -n "$TLS_NAMESPACE" create secret tls "$TLS_SECRET" \
    --cert="$CERT_SITE_DIR/$CERT_PREFIX-fullchain.crt" \
    --key="$CERT_SITE_DIR/$CERT_PREFIX.key" --dry-run=client -o yaml |
    kubectl --context "$KUBE_CONTEXT" apply -f -
)
```

- Keycloak: `etch-sso/keycloak-tls`를 등록합니다.
- Headlamp: `headlamp/headlamp-tls`를 등록합니다.
- 기존 Ingress가 이 Secret을 사용하면 Traefik이 변경을 반영합니다. 실제 접속 검증은 다음 단계에서 합니다.

Keycloak 최초 배포는 앞의 `make keycloak-check` → `make keycloak-up`으로 진행할 수 있습니다.
**갱신 시에는 위 Secret 등록을 먼저 수행합니다.** Keycloak 배포 도구는 기존 Secret과 파일이 다르면
자동으로 덮어쓰지 않고 중단하기 때문입니다. TLS 갱신만 하는 경우 앱 전체를 다시 배포할 필요는 없습니다.

Headlamp 최초 배포나 설정 변경은 [OIDC 가이드](../../headlamp/OIDC.md)의 준비를 완료한 뒤 실행합니다.

```bash
make headlamp-check
make headlamp-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

### 6. 실제 제공되는 인증서 확인

현재 터미널에서 선택한 사이트의 파일과 실제 서버 인증서의 SHA-256 지문을 비교합니다.
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
  openssl x509 -in "$CERT_SITE_DIR/$CERT_PREFIX-fullchain.crt" \
    -noout -fingerprint -sha256 > "$cert_work/expected.txt"
  openssl x509 -in "$cert_work/live-chain.pem" \
    -noout -fingerprint -sha256 > "$cert_work/actual.txt"
  cmp "$cert_work/expected.txt" "$cert_work/actual.txt"
  echo 'HTTPS 체인·도메인 검증 및 서버 인증서 일치 확인 완료'
)
```

성공 후 브라우저에서 해당 사이트를 확인합니다.
지문이 다르면 반영 대기 여부·DNS 대상·Ingress의 TLS Secret 이름을 확인합니다.
문제가 생겨 이전 인증서로 복구해야 한다면, 앞서 보관한 유효한 인증서·개인키 쌍을
5번의 `--cert`와 `--key`에 지정해 다시 등록합니다. 원본 PFX 파일은 계속 보관합니다.

### 7. Headlamp OIDC용 CA는 별도 등록

HTTPS TLS Secret 등록과 Keycloak 로그인용 CA 등록은 별개입니다.
[OIDC 가이드 3-1·3-2](../../headlamp/OIDC.md)의 명령으로 다음을 준비합니다.

- 입력: `ca/SECDS-T2RootCA.crt`, `ca/SECDS-T2IssuingCA.crt`
- 생성 파일: `etch-sso.samsungds.net/keycloak-ca-bundle.pem`
- Headlamp 등록: `headlamp` namespace의 `headlamp-oidc-ca` ConfigMap
- API server: 같은 CA 묶음을 각 제어면에 배치·마운트하고 OIDC 인증 설정에 연결

CA 교체 시에는 Headlamp와 각 API server의 신뢰 설정도 갱신해야 합니다.
Headlamp는 새 CA를 확실히 읽도록 다음 명령으로 재시작하고 로그인까지 확인합니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n headlamp rollout restart deployment/headlamp
kubectl --context "$KUBE_CONTEXT" -n headlamp rollout status deployment/headlamp --timeout=300s
```

명령 참고: [OpenSSL PFX 추출](https://docs.openssl.org/3.0/man1/openssl-pkcs12/),
[P7B 추출](https://docs.openssl.org/3.0/man1/openssl-pkcs7/).
