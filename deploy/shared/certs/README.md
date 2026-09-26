# 서버 인증서 보관 폴더

실제 서버에 저장소를 준비한 뒤 **사이트에 맞는 하위 폴더에 파일을 넣습니다.**
Keycloak과 Headlamp의 인증서·개인키는 도메인별로 구분하고 공용 CA는 `ca/`에 둡니다.
`.gitignore`, 이 README와 폴더 유지용 `.gitkeep`만 Git으로 관리합니다. 실제 인증서 파일은 모두 제외합니다.

처음에는 아래 순서로 읽습니다.

- **사전 준비**: 원본 PFX/P7B와 공용 CA 파일 배치
- **1단계. 인증서 추출**: 사이트 선택 → 추출·검증 → 결과 파일 저장
- **2단계. 서버 적용**: 클러스터 선택 → TLS Secret 등록 → HTTPS 확인 및 OIDC용 CA 설정

처음 진행하고 **PFX/P7B와 CA 원본만 있는 경우**에는 다음 순서를 따릅니다.

1. 사전 준비에서 원본 파일 위치를 확인합니다.
2. **1-1 → 1-3**을 실행해 Keycloak 인증서를 추출합니다. 1-2는 선택 사항입니다.
3. 1-1에서 Headlamp 도메인을 선택하고 **1-3을 다시 실행**합니다.
4. 두 도메인 폴더에 결과 파일이 생겼으면 **2단계를 사이트별로 한 번씩** 진행합니다.

명령은 코드 블록 단위로 복사합니다. `(`로 시작하는 블록은 마지막 `)`까지 한 번에 실행합니다.
오류가 나오면 그 단계에서 원인을 해결한 뒤 다시 실행합니다.
터미널을 새로 열었거나 다른 폴더로 이동했다면 저장소 루트로 돌아와 사이트·경로 설정부터 다시 실행합니다.

## 준비할 원본과 생성될 파일

```text
deploy/shared/certs/
├── README.md
├── .gitignore
├── etch-sso.samsungds.net/       # Keycloak
│   ├── .gitkeep
│   ├── etch-sso.samsungds.net.p7b
│   ├── etch-sso.samsungds.net.pfx
│   ├── fullchain.crt           # 1단계에서 생성
│   ├── private.key             # 1단계에서 생성
│   └── keycloak-ca-bundle.pem   # OIDC 가이드에서 나중에 생성
├── etch.samsungds.net/           # Headlamp 접속 도메인
│   ├── .gitkeep
│   ├── etch.samsungds.net.p7b
│   ├── etch.samsungds.net.pfx
│   ├── fullchain.crt           # 1단계에서 생성
│   └── private.key             # 1단계에서 생성
└── ca/                          # 공용 인증기관 원본
    ├── .gitkeep
    ├── SECDS-T2IssuingCA.crt
    └── SECDS-T2RootCA.crt
```

파일 이름은 위와 같이 유지합니다. 기존에 공용 폴더 바로 아래 넣었다면 위 구조에 맞춰 이동합니다. `fullchain.crt`와 `private.key`는 1단계에서 생성합니다. 이미 추출한 파일이 있다면 기존 파일 검증 후 서버 적용으로 진행합니다.

두 사이트 모두 인증서는 `fullchain.crt`, 개인키는 `private.key`입니다. 도메인은 상위 폴더로 구분합니다.
원본 PFX/P7B와 CA 파일 이름은 변경하지 않습니다.

| 파일 | 용도 |
| --- | --- |
| `etch-sso.samsungds.net.p7b`, `etch-sso.samsungds.net.pfx` | Keycloak 인증서 발급 원본 보관 |
| `fullchain.crt` | Keycloak HTTPS 서버 인증서와 중간 인증서 체인 |
| `private.key` | Keycloak 인증서와 짝인 개인키 |
| `SECDS-T2IssuingCA.crt` | 중간 인증기관 인증서 |
| `SECDS-T2RootCA.crt` | 루트 인증기관 인증서 |
| `etch.samsungds.net.p7b`, `etch.samsungds.net.pfx` | Headlamp 접속 도메인의 인증서 발급 원본 보관 |
| `fullchain.crt` | Headlamp HTTPS 서버 인증서와 중간 인증서 체인 |
| `private.key` | Headlamp 인증서와 짝인 개인키 |

CA 파일은 나중에 Keycloak 인증서를 신뢰하기 위한 CA 묶음을 만들 때 사용합니다.
확장자만으로 PEM/DER 형식을 확정할 수 없으므로 실제 파일을 넣은 뒤 형식과 체인을 확인합니다.

## 사전 준비: 원본 파일 배치

### 준비 A. 터미널 위치와 OpenSSL 확인

CP1에 접속해 Bash 터미널을 열고, 저장소를 내려받은 폴더로 이동합니다.
이 문서의 모든 명령은 `Makefile`과 `deploy/`가 있는 **저장소 루트**를 기준으로 합니다.

```bash
pwd
ls -d Makefile deploy/shared/certs
openssl version
```

**확인할 결과:** `Makefile`, `deploy/shared/certs`와 OpenSSL 버전이 표시됩니다.
경로를 찾지 못하면 저장소 위치를 먼저 확인합니다. `openssl: command not found`라면 서버의 OpenSSL 설치가 필요합니다.
PFX 발급 시 받은 비밀번호도 준비합니다.

### 준비 B. 원본 파일 넣기

먼저 보관 폴더를 준비합니다. 이미 폴더가 있어도 아래 명령을 실행할 수 있습니다.

```bash
mkdir -p deploy/shared/certs/{etch-sso.samsungds.net,etch.samsungds.net,ca}
chmod 700 deploy/shared/certs deploy/shared/certs/{etch-sso.samsungds.net,etch.samsungds.net,ca}
```

평소 사용하는 파일 전송 도구로 다음 파일을 넣습니다. 이미 배치했다면 이름과 위치만 확인합니다.

| 넣을 폴더 | 넣을 원본 파일 |
| --- | --- |
| `deploy/shared/certs/etch-sso.samsungds.net/` | `etch-sso.samsungds.net.pfx`, `etch-sso.samsungds.net.p7b` |
| `deploy/shared/certs/etch.samsungds.net/` | `etch.samsungds.net.pfx`, `etch.samsungds.net.p7b` |
| `deploy/shared/certs/ca/` | `SECDS-T2IssuingCA.crt`, `SECDS-T2RootCA.crt` |

아직 `fullchain.crt`, `private.key`, `keycloak-ca-bundle.pem`이 없어도 정상입니다.
이미 추출한 `fullchain.crt`와 `private.key`를 사용하려면 해당 사이트 폴더에 함께 넣습니다.

### 준비 C. 파일 권한 설정

원본 파일을 넣은 뒤 PFX의 읽기 권한을 소유자로 제한합니다. 추출 시 개인키 권한은 자동으로 설정됩니다.

```bash
chmod 600 deploy/shared/certs/etch-sso.samsungds.net/etch-sso.samsungds.net.pfx \
  deploy/shared/certs/etch.samsungds.net/etch.samsungds.net.pfx
```

파일은 배포 명령을 실행하는 계정이 읽을 수 있어야 합니다.
Git으로 실제 인증서가 전송되지는 않으므로 서버마다 필요한 파일은 별도로 넣습니다.
**다음:** 원본에서 새로 추출하려면 1-1 → 1-3, 기존 결과 파일을 사용하려면 1-1 → 1-4로 진행합니다.

## 1단계. 인증서 추출

아래 명령은 **CP1의 저장소 루트에서 Bash로 실행**합니다.
이미 추출한 fullchain과 개인키가 정상이라면 추출은 생략하고 검증·적용부터 진행합니다.
이 단계는 Kubernetes 접속 없이 실행할 수 있습니다. PFX 비밀번호는 명령이 물어볼 때 입력합니다.

### 1-1. 작업할 사이트 선택

처음에는 Keycloak부터 진행하면 됩니다. 아래 명령은 이번에 처리할 도메인을 터미널 변수에 저장합니다.
다음 두 블록 중 **작업할 사이트 하나만** 실행합니다. 다른 사이트도 추출하려면 1단계를 마친 뒤 다시 선택합니다.

Keycloak 인증서를 작업할 때:

```bash
CERT_SITE=etch-sso.samsungds.net
```

Headlamp 인증서를 작업할 때:

```bash
CERT_SITE=etch.samsungds.net
```

그다음 추출에 사용할 공통 경로를 설정합니다. 이후 명령은 같은 터미널에서 실행합니다.

```bash
CERT_SITE_DIR="$PWD/deploy/shared/certs/$CERT_SITE"
CERT_CA_DIR="$PWD/deploy/shared/certs/ca"
set -o pipefail
```

선택한 도메인과 입력 파일을 확인합니다.

```bash
printf '추출할 도메인: %s\n' "$CERT_SITE"
ls -l "$CERT_SITE_DIR/$CERT_SITE.pfx" \
  "$CERT_CA_DIR/SECDS-T2IssuingCA.crt" "$CERT_CA_DIR/SECDS-T2RootCA.crt"
```

**확인할 결과:** 선택한 도메인과 파일 3개의 정보가 표시됩니다.
`No such file or directory`가 나오면 파일 배치 또는 현재 터미널 위치를 확인합니다.
**다음:** 바로 추출하려면 **1-3**으로 이동합니다. 원본에 든 공개 인증서를 살펴보고 싶을 때만 1-2를 실행합니다.

### 1-2. P7B에서 공개 인증서 묶음 확인 — 필요한 경우

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

### 1-3. PFX에서 서버 인증서·개인키 추출, 검증 후 저장

이 블록 하나가 다음 작업을 순서대로 수행합니다.

1. 공용 CA를 읽을 수 있는 PEM 형식으로 준비합니다.
2. PFX에서 서버 인증서와 개인키를 꺼냅니다.
3. 도메인·유효기간·CA 체인과 인증서/개인키의 일치를 검사합니다.
4. 서버 인증서와 중간 CA를 합친 `fullchain.crt`, 개인키인 `private.key`를 저장합니다.

아래 블록 전체를 복사해 실행합니다. `Enter Import Password:`가 나오면 **선택한 사이트의 PFX 비밀번호**를 입력하고 Enter를 누릅니다.
입력 중 글자나 별표가 보이지 않아도 정상입니다. 인증서와 개인키를 각각 꺼내므로 같은 비밀번호를 두 번 입력합니다.
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
  for cert_name in "fullchain.crt" "private.key"; do
    if [ -f "$CERT_SITE_DIR/$cert_name" ]; then
      cp -p "$CERT_SITE_DIR/$cert_name" "$cert_backup/"
    fi
  done
  install -m 0600 "$cert_work/private.key" "$CERT_SITE_DIR/private.key"
  install -m 0644 "$cert_work/fullchain.crt" "$CERT_SITE_DIR/fullchain.crt"
  printf '추출·검증 완료. 기존 파일 보관 위치: %s\n' "$cert_backup"
)
```

**성공 기준:** `leaf.crt: OK`와 `추출·검증 완료`가 표시됩니다.
`cmp`는 두 공개키가 같으면 아무 출력 없이 성공합니다. 오류가 나면 등록 단계로 넘어가지 않습니다.

생성된 파일은 내용 대신 이름과 권한으로 확인합니다.

```bash
ls -l "$CERT_SITE_DIR/fullchain.crt" "$CERT_SITE_DIR/private.key"
```

**확인할 결과:** 파일 2개가 표시되고 `private.key`의 권한은 `-rw-------`입니다.
서버 인증서는 `fullchain.crt`의 첫 번째 인증서로 들어 있으며, 별도 `leaf.crt`는 임시 작업 후 삭제됩니다.
루트 CA는 `fullchain.crt`에 넣지 않고 원본 `ca/SECDS-T2RootCA.crt`로 보관합니다.

**다음:** 다른 사이트도 추출하려면 1-1로 돌아가 도메인을 바꾸고 1-3을 반복합니다.
필요한 사이트를 모두 추출했다면 **1-4는 건너뛰고 2-1**로 이동합니다. 파일 생성까지만 필요하다면 여기서 마쳐도 됩니다.

OpenSSL 3에서 구형 PFX 암호의 `unsupported` 오류가 발생한 경우에만
위의 해당 `openssl pkcs12` 명령에 `-legacy`를 추가해 다시 실행합니다.
비밀번호 오류나 체인 오류에는 이 옵션을 사용하지 않습니다.
이 절차는 PFX에 서버 인증서·개인키 한 쌍이 있고 제공된 중간 CA 하나로 체인이 연결되는 경우를 기준으로 합니다.

### 1-4. 이미 추출한 파일 검증 — 추출을 생략했다면 실행

위 1-3 검증을 통과했다면 이 검사는 반복하지 않아도 됩니다.
기존 파일을 사용한다면 1-1의 사이트·경로 설정 후 개인키 권한을 제한하고 아래 검증을 실행합니다.

```bash
chmod 600 "$CERT_SITE_DIR/private.key"
```

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
    "$CERT_SITE_DIR/fullchain.crt"
  openssl x509 -in "$CERT_SITE_DIR/fullchain.crt" -pubkey -noout > "$cert_work/cert-public.pem"
  openssl pkey -in "$CERT_SITE_DIR/private.key" -passin pass: -pubout > "$cert_work/key-public.pem"
  cmp "$cert_work/cert-public.pem" "$cert_work/key-public.pem"
  echo '인증서 체인·도메인·기간·개인키 일치 확인 완료'
)
```

fullchain은 **서버 인증서가 첫 번째, 이어서 중간 CA** 순서여야 합니다.
위 검증은 별도의 CA 파일로 체인을 확인하므로 fullchain에 중간 CA가 실제로 포함돼 있는지도 확인합니다.

```bash
openssl crl2pkcs7 -nocrl -certfile "$CERT_SITE_DIR/fullchain.crt" |
  openssl pkcs7 -print_certs -noout
```

현재 구성은 서버 인증서와 `SECDS-T2IssuingCA` 두 개가 순서대로 나와야 합니다.
**성공 기준:** `인증서 체인·도메인·기간·개인키 일치 확인 완료`가 표시되고, 위 인증서 순서도 맞습니다.
**다음:** 2-1로 이동합니다.

## 2단계. 서버 적용

**1단계에서 추출·검증한 파일을 준비한 뒤 진행합니다.**
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
TLS_SECRET=keycloak-tls
```

Headlamp:

```bash
CERT_SITE=etch.samsungds.net
TLS_NAMESPACE=headlamp
TLS_SECRET=headlamp-tls
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

Secret 이름은 현재 프로젝트 기본값입니다. 운영 중인 Ingress가 다른 Secret을 참조한다면
실제 이름에 맞춰 `TLS_SECRET`을 바꾸고, Headlamp의 `HEADLAMP_TLS_SECRET`도 일치시킵니다.

등록 전에 선택한 대상과 파일 경로를 한 번 확인합니다.

```bash
printf '도메인: %s\ncontext: %s\nnamespace: %s\nSecret: %s\n' \
  "$CERT_SITE" "$KUBE_CONTEXT" "$TLS_NAMESPACE" "$TLS_SECRET"
ls -l "$CERT_SITE_DIR/fullchain.crt" "$CERT_SITE_DIR/private.key"
```

**확인할 결과:** 적용하려는 도메인·클러스터·Secret과 결과 파일 2개가 표시됩니다.
다른 대상이 표시되면 2-1에서 해당 값을 다시 설정합니다. 맞으면 2-2로 진행합니다.

### 2-2. Kubernetes TLS Secret에 등록 또는 갱신

**적용할 사이트가 1-3 또는 1-4 검증에 성공한 뒤에만 실행합니다.**
아래 명령은 2-1에서 선택한 사이트의 TLS Secret을 실제로 생성하거나 갱신합니다.
폴더에 파일을 넣는 것과 달리, 이 단계부터 서버에 반영됩니다.

```bash
(
  set -euo pipefail
  test -n "$KUBE_CONTEXT"
  kubectl --context "$KUBE_CONTEXT" create namespace "$TLS_NAMESPACE" --dry-run=client -o yaml |
    kubectl --context "$KUBE_CONTEXT" apply -f -
  kubectl --context "$KUBE_CONTEXT" -n "$TLS_NAMESPACE" create secret tls "$TLS_SECRET" \
    --cert="$CERT_SITE_DIR/fullchain.crt" \
    --key="$CERT_SITE_DIR/private.key" --dry-run=client -o yaml |
    kubectl --context "$KUBE_CONTEXT" apply -f -
)
```

**성공 기준:** `secret/keycloak-tls` 또는 `secret/headlamp-tls` 뒤에 `created`, `configured`, `unchanged` 중 하나가 표시됩니다.
오류 없이 끝났는지 확인합니다. Secret 등록 성공과 실제 HTTPS 반영 여부는 2-4에서 함께 확인합니다.

- Keycloak: `etch-sso/keycloak-tls`를 등록합니다.
- Headlamp: `etch.samsungds.net`용 `headlamp/headlamp-tls`를 등록합니다.
- Airflow: 같은 업무 도메인의 `/airflow`를 사용하며, [Airflow 배포](../../airflow/04_SETUP_FLOW.md)에서
  `AIRFLOW_TLS_SOURCE=headlamp/headlamp-tls`로 `airflow/airflow-tls`에 최초 복사합니다. 원본 갱신 시 복사본도 별도 갱신합니다.
- namespace·Ingress 이름·host·TLS Secret은 [공용 Ingress 기준](../ingress/README.md#운영-ingress-기준)을 따릅니다.
- 기존 Ingress가 이 Secret을 사용하면 Traefik이 변경을 반영합니다. 실제 접속 검증은 다음 단계에서 합니다.

### 2-3. 최초 배포 시 앱 설치

**이미 서비스가 운영 중이고 인증서만 갱신했다면 이 단계는 건너뛰고 2-4로 이동합니다.**

Keycloak 배포 도구는 `deploy/shared/certs/etch-sso.samsungds.net`을 기본으로 사용합니다.
Keycloak 최초 배포라면 기존 운영 env와 대상 context를 준비한 뒤 저장소 루트에서 실행합니다.

```bash
make keycloak-check KUBE_CONTEXT="$KUBE_CONTEXT"
```

검사가 성공한 뒤 다음 명령으로 배포합니다. 검사에 실패하면 오류를 해결한 뒤 다시 검사합니다.

```bash
make keycloak-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

**갱신 시에는 위 Secret 등록을 먼저 수행합니다.** Keycloak 배포 도구는 기존 Secret과 파일이 다르면
자동으로 덮어쓰지 않고 중단하기 때문입니다. TLS 갱신만 하는 경우 앱 전체를 다시 배포할 필요는 없습니다.

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
지문이 다르면 반영 대기 여부·DNS 대상·Ingress의 TLS Secret 이름을 확인합니다.
문제가 생겨 이전 인증서로 복구해야 한다면, 앞서 보관한 유효한 인증서·개인키 쌍을
2-2의 `--cert`와 `--key`에 지정해 다시 등록합니다. 원본 PFX 파일은 계속 보관합니다.

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

## 진행 중 막혔을 때

| 표시된 오류 또는 상황 | 먼저 확인할 내용 |
| --- | --- |
| `No such file or directory` | 저장소 루트에서 실행했는지, 해당 사이트 파일 이름과 경로가 맞는지 확인합니다. |
| PFX 비밀번호 오류 | 선택한 도메인의 PFX 비밀번호인지 확인하고 1-3을 다시 실행합니다. |
| PFX를 읽을 때 `unsupported` | 1-3의 OpenSSL 3 `-legacy` 안내를 확인합니다. |
| 인증서 검증 실패 | 선택한 도메인, 인증서 유효기간, 함께 발급받은 CA 원본이 맞는지 확인합니다. |
| `cmp`에서 파일이 다르다고 표시됨 | 1단계라면 인증서와 개인키의 짝을, 2-4라면 실제 서버가 제공하는 인증서를 확인합니다. |
| `kubectl` 인증 또는 권한 오류 | 2-1에서 선택한 context와 해당 계정의 접근 권한을 확인합니다. |
| HTTPS 연결 실패 | DNS가 가리키는 서버, 443 포트 연결, 서비스·Ingress 배포 상태를 확인합니다. |

## 참고: 이전 파일 이름을 사용하던 서버

처음 원본 파일을 배치하는 경우에는 이 항목을 실행하지 않아도 됩니다.

### 기존 서버 파일 이름 변경

이전 이름으로 파일을 넣은 서버에서는 저장소 루트에서 한 번 실행합니다.
대상 파일이 이미 있으면 덮어쓰지 않고 중단합니다. 해당 경우 두 파일 중 사용할 인증서를 먼저 확인합니다.
파일 이름만 바꾸므로 기존 Kubernetes TLS Secret이나 서비스는 변경되지 않습니다.

```bash
(
  set -euo pipefail
  cert_root=deploy/shared/certs
  cert_moves=(
    'etch-sso.samsungds.net/keycloak-fullchain.crt etch-sso.samsungds.net/fullchain.crt'
    'etch-sso.samsungds.net/keycloak.key etch-sso.samsungds.net/private.key'
    'etch.samsungds.net/etch-fullchain.crt etch.samsungds.net/fullchain.crt'
    'etch.samsungds.net/etch.key etch.samsungds.net/private.key'
  )
  for cert_move in "${cert_moves[@]}"; do
    read -r cert_old cert_new <<< "$cert_move"
    if [ -e "$cert_root/$cert_old" ]; then
      test ! -e "$cert_root/$cert_new"
    fi
  done
  for cert_move in "${cert_moves[@]}"; do
    read -r cert_old cert_new <<< "$cert_move"
    if [ -e "$cert_root/$cert_old" ]; then
      mv -n -- "$cert_root/$cert_old" "$cert_root/$cert_new"
    fi
  done
)
```

명령 참고: [OpenSSL PFX 추출](https://docs.openssl.org/3.0/man1/openssl-pkcs12/),
[P7B 추출](https://docs.openssl.org/3.0/man1/openssl-pkcs7/).
