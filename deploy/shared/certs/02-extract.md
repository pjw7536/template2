# 인증서 추출과 검증

[인증서 안내](README.md) · [원본 준비](01-prepare.md) · [추출·검증](02-extract.md) · [서버 적용](03-apply.md)

[원본 준비](01-prepare.md)를 마친 후 진행합니다.

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
필요한 사이트를 모두 추출했다면 **[서버 적용의 2-1](03-apply.md#2-1-적용할-사이트와-대상-클러스터-선택)**로 이동합니다. 파일 생성까지만 필요하다면 여기서 마쳐도 됩니다.

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

**다음:** [서버 적용의 2-1](03-apply.md#2-1-적용할-사이트와-대상-클러스터-선택)로 이동합니다.
