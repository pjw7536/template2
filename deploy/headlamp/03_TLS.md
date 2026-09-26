# 03. 사이트 HTTPS와 Keycloak CA

[전체 순서](README.md) · 이전: [01 준비](01_SERVER_SETUP.md) · 다음: [04 Keycloak](04_KEYCLOAK_SETUP.md)

01에서 읽은 변수와 대상 context를 유지합니다. 새 터미널에서는 [실행 입력](01_SERVER_SETUP.md#2-대상-context와-실행-입력)을 먼저 준비합니다.
아래는 현재 사내 루트·중간 CA를 사용하는 설치 절차입니다.
다른 인증기관이나 공인 CA를 쓰면 먼저 이 문서 끝의 해당 분기를 읽고 입력·생략 단계를 맞춥니다.

**실행 위치:** 01에서 사용하던 CP1 Bash 터미널, 저장소 루트.
**목표:** Headlamp용 사이트 인증서와 Keycloak을 신뢰할 CA를 `headlamp` namespace에 등록합니다.
운영 도메인은 `etch.samsungds.net`, TLS Secret은 `headlamp/headlamp-tls`입니다.
Keycloak의 `etch-sso.samsungds.net` 인증서와 구분해 준비합니다.

먼저 아래에서 사용할 경로가 준비됐는지 확인합니다. 출력값이 비어 있으면 01의 실행 입력부터 다시 수행하세요.
단, 공인 CA 분기에서는 `HEADLAMP_OIDC_CA_FILE`이 빈 값인 것이 정상입니다.

```bash
printf '사이트 도메인: %s\n사이트 인증서 폴더: %s\nCA 원본 폴더: %s\nKeycloak CA 묶음: %s\n' \
  "$HEADLAMP_HOST" "$HEADLAMP_CERT_DIR" "$HEADLAMP_CA_DIR" "$HEADLAMP_OIDC_CA_FILE"
```

기본 사내 CA를 사용하면 아래 1~3번을 진행합니다. Keycloak 또는 Headlamp 인증서의 발급기관이 다르면
**명령을 실행하기 전에** 끝의 [공개 CA 또는 다른 인증기관인 경우](#공개-ca-또는-다른-인증기관인-경우)를 확인합니다.

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

파일은 관리자 PC가 아니라 **지금 명령을 실행하는 CP1의 위 경로**에 있어야 합니다.
인증서 담당자에게 받은 파일을 서버로 옮기고 표의 이름으로 배치한 뒤 확인합니다.

```bash
ls -l "$HEADLAMP_CERT_DIR/fullchain.crt" "$HEADLAMP_CERT_DIR/private.key" \
  "$HEADLAMP_CA_DIR/SECDS-T2RootCA.crt" "$HEADLAMP_CA_DIR/SECDS-T2IssuingCA.crt"
```

네 파일 모두 조회되어야 합니다. `No such file`이면 아직 검증 명령을 실행하지 말고 경로·파일명을 맞춥니다.
`fullchain.crt`는 Headlamp 도메인에 유효한 인증서여야 하며, Keycloak 사이트 인증서를 이름만 바꿔 사용하지 않습니다.

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
`hostname mismatch`는 사이트 도메인과 인증서가 다르다는 뜻이고, `unable to get ... issuer certificate`는
CA 체인을 확인해야 한다는 뜻입니다. `cmp`에서 차이가 나면 인증서와 개인키가 서로 짝이 맞지 않습니다.
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

등록 시 `created`, `configured` 또는 `unchanged`가 출력되면 적용된 것입니다.
마지막 명령은 `OIDC 연결 검사 통과: TLS·issuer·code flow·PKCE S256·RS256 공개키`를 출력해야 합니다.

| 여기서 실패한다면 | 확인할 것 |
| --- | --- |
| Secret·ConfigMap이 `NotFound` | 등록 명령 성공 여부, context, `headlamp` namespace, 01에서 읽은 이름 |
| 이름을 찾지 못함·연결 시간 초과 | CP1에서 Keycloak 도메인의 DNS·방화벽·HTTPS 접근 |
| TLS 인증서 검증 실패 | Keycloak의 실제 발급 CA가 준비한 루트·중간 CA와 같은지, 인증서 유효기간 |
| issuer 불일치 | env의 issuer가 Keycloak 공개 URL + `/realms/etch`와 정확히 같은지 |

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
