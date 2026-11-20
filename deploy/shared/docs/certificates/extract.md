# 인증서 추출과 검증

[가이드 홈](../README.md#https인증서) · 이전: [원본 준비](prepare.md) · 다음: [공용 TLS 등록](../../../README.md#공용-tls-등록) → [등록 뒤 확인](apply.md)

**목적:** PFX에서 서버 인증서·개인키를 꺼내 도메인·기간·CA 체인·키 일치를 검증하고 `fullchain.crt`, `private.key`로 저장합니다.
**준비물:** [원본 준비](prepare.md)를 마친 사이트 폴더와 CA, PFX 비밀번호 파일.
**실행 위치:** 관리 호스트의 저장소 루트에서 Bash. Kubernetes 접속은 필요하지 않습니다.

이미 추출한 fullchain과 개인키가 있다면 3단계를 건너뛰고 4단계로 검증합니다.

**PFX 비밀번호:** 명령은 비밀번호를 묻지 않고 `-passin file:<비밀번호 파일>`로 파일의 첫 줄을 읽습니다. 비밀번호 파일은 [인증서 발급](../infrastructure/access.md#인증서-발급) 절의 방법으로 저장소 밖 경로에 권한 `0600`으로 전달받고, 그 사이트의 추출이 끝나면 [5단계](#5-비밀번호-파일-삭제)에서 지웁니다. 비밀번호 값을 명령줄·응답·운영 기록에 쓰지 않습니다.

## 1. 작업할 사이트 선택

블록마다 새 셸이므로 아래 값을 각 블록의 자리표시에 직접 씁니다. 한 번에 사이트 하나를 끝까지 진행하고, 다른 사이트는 1단계부터 다시 합니다.

| 자리표시 | 값 |
| --- | --- |
| `<사이트>` | Keycloak 인증서는 `sso.etch.samsungds.net`, 공용 SAN 인증서는 `etch.samsungds.net` |
| `<비밀번호 파일>` | 그 사이트 PFX의 비밀번호가 첫 줄에 있는 파일의 절대 경로 |

[조회] 선택한 사이트의 입력 파일을 확인합니다.

```bash
CERT_SITE=<사이트>
printf '추출할 도메인: %s\n' "$CERT_SITE"
ls -l "deploy/shared/certs/$CERT_SITE/$CERT_SITE.pfx" \
  deploy/shared/certs/ca/SECDS-T2IssuingCA.crt deploy/shared/certs/ca/SECDS-T2RootCA.crt
test -s "<비밀번호 파일>" && echo '비밀번호 파일 있음'
```

**기대 결과:** 선택한 도메인과 파일 3개의 정보, `비밀번호 파일 있음`이 표시됩니다. 기존 파일만 검증(4단계)할 때는 PFX와 비밀번호 파일이 없어도 됩니다.
**실패 확인:** `No such file or directory`가 나오면 파일 배치([원본 준비](prepare.md#2-폴더-준비와-원본-배치))와 실행 위치(저장소 루트)를 확인합니다. 비밀번호 파일이 없으면 [인증서 발급](../infrastructure/access.md#인증서-발급) 절의 방법으로 받습니다.

**다음:** 바로 추출하려면 3단계, 기존 파일을 쓰려면 4단계로 이동합니다. 원본의 공개 인증서를 살펴볼 때만 2단계를 실행합니다.

## 2. P7B에서 공개 인증서 묶음 확인 — 필요한 경우

P7B에는 개인키가 없습니다. 서버 인증서·CA가 어떤 순서로 들어 있는지 확인할 때 사용합니다.

[변경] 사이트 폴더에 `p7b-certificates.pem`을 만들고 내용을 출력합니다. PEM으로 먼저 읽고, 실패하면 DER로 다시 읽습니다.

```bash
(
  set -euo pipefail
  CERT_SITE=<사이트>
  CERT_SITE_DIR="$PWD/deploy/shared/certs/$CERT_SITE"
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

[변경] PFX에 들어 있는 CA만 별도로 확인하려면 다음 명령으로 사이트 폴더에 `pfx-ca-certificates.pem`을 만듭니다.
CA가 포함되지 않은 PFX라면 결과에 인증서가 없을 수 있습니다.

```bash
CERT_SITE=<사이트>
openssl pkcs12 -in "deploy/shared/certs/$CERT_SITE/$CERT_SITE.pfx" -passin "file:<비밀번호 파일>" \
  -cacerts -nokeys -out "deploy/shared/certs/$CERT_SITE/pfx-ca-certificates.pem"
grep -c 'BEGIN CERTIFICATE' "deploy/shared/certs/$CERT_SITE/pfx-ca-certificates.pem"
```

마지막 줄은 PFX에 들어 있는 CA 인증서 수입니다.

## 3. PFX에서 서버 인증서·개인키 추출, 검증 후 저장

이 블록 하나가 다음 작업을 순서대로 수행합니다.

1. 공용 CA를 읽을 수 있는 PEM 형식으로 준비합니다.
2. PFX에서 서버 인증서와 개인키를 꺼냅니다.
3. 도메인·유효기간·CA 체인과 인증서/개인키의 일치를 검사합니다.
4. 서버 인증서와 중간 CA를 합친 `fullchain.crt`, 개인키인 `private.key`를 저장합니다.

임시 폴더에서 추출·검증한 뒤에만 정식 파일로 저장합니다.
기존 파일은 해당 사이트의 `backups/` 아래에 보관합니다.

[변경] `<사이트>`와 `<비밀번호 파일>`을 바꿔 블록 전체를 실행합니다. 입력을 묻지 않습니다.

```bash
(
  set -euo pipefail
  umask 077
  CERT_SITE=<사이트>
  CERT_PASS_FILE="<비밀번호 파일>"
  CERT_SITE_DIR="$PWD/deploy/shared/certs/$CERT_SITE"
  CERT_CA_DIR="$PWD/deploy/shared/certs/ca"
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

  # 비밀번호는 파일의 첫 줄에서 읽습니다.
  openssl pkcs12 -in "$CERT_SITE_DIR/$CERT_SITE.pfx" -passin "file:$CERT_PASS_FILE" -clcerts -nokeys |
    openssl x509 -out "$cert_work/leaf.crt"
  openssl pkcs12 -in "$CERT_SITE_DIR/$CERT_SITE.pfx" -passin "file:$CERT_PASS_FILE" -nocerts -nodes |
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

**기대 결과:** `leaf.crt: OK`와 `추출·검증 완료`가 표시됩니다. `cmp`는 두 공개키가 같으면 출력 없이 성공합니다.
**실패 확인:** 오류가 나면 정식 파일은 바뀌지 않습니다. 공용 TLS 등록으로 넘어가지 않고 아래 [문제 해결](#문제-해결)을 확인합니다.

[조회] 생성된 파일은 내용 대신 이름과 권한으로 확인합니다.

```bash
CERT_SITE=<사이트>
ls -l "deploy/shared/certs/$CERT_SITE/fullchain.crt" "deploy/shared/certs/$CERT_SITE/private.key"
```

**기대 결과:** 파일 2개가 표시되고 `private.key`의 권한은 `-rw-------`입니다.
서버 인증서는 `fullchain.crt`의 첫 번째 인증서로 들어 있으며, 별도 `leaf.crt`는 임시 작업 후 삭제됩니다.
루트 CA는 `fullchain.crt`에 넣지 않고 원본 `ca/SECDS-T2RootCA.crt`로 보관합니다.

**다음:** [5단계](#5-비밀번호-파일-삭제)로 비밀번호 파일을 지웁니다. 다른 사이트는 1단계로 돌아가 `<사이트>`를 바꾸고 3단계를 반복합니다. 모두 추출했다면 [다음 단계](#다음-단계)로 갑니다.

OpenSSL 3에서 구형 PFX 암호의 `unsupported` 오류가 발생한 경우에만
위의 두 `openssl pkcs12` 명령에 `-legacy`를 추가해 다시 실행합니다.
비밀번호 오류나 체인 오류에는 이 옵션을 사용하지 않습니다.
이 절차는 PFX에 서버 인증서·개인키 한 쌍이 있고 제공된 중간 CA 하나로 체인이 연결되는 경우를 기준으로 합니다.

## 4. 이미 추출한 파일 검증 — 추출을 생략했다면 실행

3단계 검증을 통과했다면 반복하지 않아도 됩니다. 기존 파일을 사용한다면 개인키 권한을 제한하고 검증합니다.

[변경] 개인키 권한을 `600`으로 바꾸고 체인·도메인·기간·키 일치를 검사합니다. 인증서 내용은 바꾸지 않습니다.

```bash
(
  set -euo pipefail
  CERT_SITE=<사이트>
  CERT_SITE_DIR="$PWD/deploy/shared/certs/$CERT_SITE"
  CERT_CA_DIR="$PWD/deploy/shared/certs/ca"
  chmod 600 "$CERT_SITE_DIR/private.key"
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

[조회]

```bash
CERT_SITE=<사이트>
openssl crl2pkcs7 -nocrl -certfile "deploy/shared/certs/$CERT_SITE/fullchain.crt" |
  openssl pkcs7 -print_certs -noout
```

현재 구성은 서버 인증서와 `SECDS-T2IssuingCA` 두 개가 순서대로 나와야 합니다.

**기대 결과:** `인증서 체인·도메인·기간·개인키 일치 확인 완료`가 표시되고, 위 인증서 순서도 맞습니다.

## 5. 비밀번호 파일 삭제

[변경] 그 사이트의 추출이 끝나면 비밀번호 파일을 지웁니다. 원본 PFX는 계속 보관합니다.

```bash
rm -f "<비밀번호 파일>"
test ! -e "<비밀번호 파일>" && echo '비밀번호 파일 삭제 완료'
```

성공: `비밀번호 파일 삭제 완료`.

## 다음 단계

추출·검증을 마친 `fullchain.crt`·`private.key`는 그 host를 쓰는 앱의 `make ops-deploy`가 준비 검사에서 공용 Traefik에 자동으로 등록합니다.
직접 등록하거나 갱신하려면 [공용 TLS 등록](../../../README.md#공용-tls-등록)을, 등록 뒤 실제로 제공되는 인증서의 확인은 [인증서 적용](apply.md#3-실제-제공-인증서-확인--관리-호스트)을 따릅니다.

## 문제 해결

| 표시된 오류 또는 상황 | 먼저 확인할 내용 |
| --- | --- |
| `No such file or directory` | 저장소 루트에서 실행했는지, 해당 사이트 파일 이름과 경로가 맞는지 확인합니다. |
| PFX 비밀번호 오류(`Mac verify error: invalid password?`) | 비밀번호 파일의 첫 줄이 선택한 사이트 PFX의 비밀번호인지 확인합니다. 맞는 값을 알 수 없으면 [인증서 발급](../infrastructure/access.md#인증서-발급) 절의 방법으로 다시 받고 3단계를 다시 실행합니다. |
| PFX를 읽을 때 `unsupported` | 3단계의 OpenSSL 3 `-legacy` 안내를 확인합니다. |
| 인증서 검증 실패 | 선택한 도메인, 인증서 유효기간, 함께 발급받은 CA 원본이 맞는지 확인합니다. |
| `cmp`에서 파일이 다르다고 표시됨 | 인증서와 개인키가 같은 발급 건의 짝인지 확인합니다. |
