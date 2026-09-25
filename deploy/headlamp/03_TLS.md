# 03. 사이트 HTTPS와 Keycloak CA

[전체 순서](README.md) · 이전: [01 준비](01_SERVER_SETUP.md) · 다음: [04 Keycloak](04_KEYCLOAK_SETUP.md)

01에서 읽은 변수와 대상 context를 유지합니다. 새 터미널에서는 [실행 입력](01_SERVER_SETUP.md#2-대상-context와-실행-입력)을 먼저 준비합니다.
아래는 현재 사내 루트·중간 CA를 사용하는 설치 절차입니다.
다른 인증기관이나 공인 CA를 쓰면 먼저 이 문서 끝의 해당 분기를 읽고 입력·생략 단계를 맞춥니다.

| 구성 | 용도 | 적용 위치 |
| --- | --- | --- |
| Headlamp fullchain·개인키 | 브라우저에 Headlamp 사이트 증명 | `headlamp` namespace의 TLS Secret |
| Keycloak CA 묶음 | Headlamp가 Keycloak HTTPS 신뢰 | `headlamp` namespace의 ConfigMap |
| 같은 Keycloak CA 묶음 | Kubernetes가 Keycloak 토큰 서명키 조회 | 05에서 모든 API server에 파일·마운트 등록 |

## 1. 필요한 파일 준비

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

**이미 위 파일이 있으면 PFX·P7B는 필요하지 않습니다. Keycloak 서버 개인키도 가져올 필요가 없습니다.**
원본 PFX만 있다면 [공용 인증서 추출](../shared/certs/README.md#원본에서-추출하고-서버에-적용하기)의
사이트 선택과 3번 추출 절차를 수행한 뒤 여기로 돌아옵니다. 그 문서의 앱 배포 단계까지 진행하지 않습니다.
사이트 이름·Secret·context는 01에서 선택한 값과 같아야 합니다.

## 2. 인증서 검증과 CA 묶음 생성

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

`fullchain.crt: OK`와 완료 메시지가 나와야 합니다. 오류가 나면 다음 단계로 넘어가지 않습니다.
fullchain은 별도 CA 파일로 검증했으므로 중간 CA 포함 여부도 확인합니다.

```bash
openssl crl2pkcs7 -nocrl -certfile "$HEADLAMP_CERT_DIR/fullchain.crt" |
  openssl pkcs7 -print_certs -noout
```

현재 체인에서는 Headlamp 서버 인증서와 중간 CA가 순서대로 나와야 합니다. 루트 CA는 fullchain에 넣지 않습니다.

## 3. TLS Secret과 OIDC CA 등록

```bash
(
  set -euo pipefail
  kubectl --context "$KUBE_CONTEXT" -n headlamp create secret tls "$HEADLAMP_TLS_SECRET" \
    --cert="$HEADLAMP_CERT_DIR/fullchain.crt" --key="$HEADLAMP_CERT_DIR/private.key" \
    --dry-run=client -o yaml | kubectl --context "$KUBE_CONTEXT" apply -f -
  test -n "$HEADLAMP_OIDC_CA_CONFIGMAP"
  kubectl --context "$KUBE_CONTEXT" -n headlamp create configmap "$HEADLAMP_OIDC_CA_CONFIGMAP" \
    --from-file=ca.crt="$HEADLAMP_OIDC_CA_FILE" --dry-run=client -o yaml |
    kubectl --context "$KUBE_CONTEXT" apply -f -
)
```

```bash
kubectl --context "$KUBE_CONTEXT" -n headlamp get secret "$HEADLAMP_TLS_SECRET"
kubectl --context "$KUBE_CONTEXT" -n headlamp get configmap "$HEADLAMP_OIDC_CA_CONFIGMAP"
make headlamp-oidc-check HEADLAMP_OIDC_CA_FILE="$HEADLAMP_OIDC_CA_FILE"
```

접속 중인 Keycloak의 TLS 체인·issuer·code flow·S256·RS256 공개키까지 확인합니다.
실행 서버에서 성공해도 Pod·API server의 네트워크·CA 신뢰는 각각 준비해야 합니다.
검사는 실제 client secret·로그인 토큰·RBAC까지 확인하지 않습니다.
브라우저 PC의 CA 신뢰는 [클라이언트 신뢰 안내](../keycloak/03_TLS.md)를 참고합니다.

**완료 기준:** TLS Secret·OIDC CA ConfigMap이 조회되고 OIDC 연결 검사가 통과합니다.
다음 [04 Keycloak](04_KEYCLOAK_SETUP.md)으로 진행합니다. Headlamp의 실제 HTTPS 확인은 배포 후 06에서 합니다.

## 공개 CA 또는 다른 인증기관인 경우

위 명령은 현재 사내 CA 두 파일을 기준으로 합니다. 다른 CA라면 발급기관이 제공한 체인과 파일명으로
2번을 맞추고 두 서비스가 서로 다른 CA를 쓰면 사이트 검증용 CA와 Keycloak 신뢰용 CA를 분리합니다.
Keycloak이 공인 CA를 사용하고 클라이언트 기본 신뢰로 검증된다면 `HEADLAMP_OIDC_CA_CONFIGMAP`을 비우고
01의 입력을 다시 읽습니다. Keycloak CA 생성·ConfigMap 등록·05의 OIDC CA 파일 옵션은 생략하고
`make headlamp-oidc-check`를 CA 인자 없이 실행합니다. 사이트 TLS Secret 등록은 여전히 필요합니다.

공식 참고: [OpenSSL 인증서 검증](https://docs.openssl.org/3.0/man1/openssl-verification-options/).
