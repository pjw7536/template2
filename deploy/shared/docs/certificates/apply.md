# 인증서 서버 적용과 갱신

[가이드 홈](../README.md#https인증서) · 이전: [추출·검증](extract.md) · [원본 준비](prepare.md)

**목적:** 검증한 인증서를 공용 Traefik의 `etch-sso/traefik-tls` Secret에 등록·갱신하고, 실제로 제공되는 인증서를 확인합니다.
**준비물:** [추출·검증](extract.md)에 성공한 `fullchain.crt`·`private.key` 또는 기존 `kubernetes.io/tls` Secret, 대상 클러스터 context와 TLS Secret 등록 권한.
**실행 위치:** CP1의 저장소 루트에서 Bash. 폴더에 파일을 넣는 것만으로 서버 인증서나 Secret은 바뀌지 않습니다.

- 모든 앱은 같은 공용 Secret을 사용하며 Ingress에는 Secret 이름을 지정하지 않습니다. 인증서를 앱 namespace에 복제하지 않습니다.
- 하나의 SAN 인증서가 여러 host를 포함해도 host별로 1~3단계를 반복합니다.
- 공개 host 목록은 [서비스 원본](../infrastructure/services.md#공개-도메인과-인증)을 따릅니다.

## 1. 적용할 사이트와 대상 클러스터 선택

`CERT_SITE`는 인증서 원본 폴더, `TLS_HOST`는 SAN에 포함되어야 하는 실제 공개 host입니다. 두 블록 중 하나만 실행합니다.

```bash
# 별도 SSO 인증서
CERT_SITE=sso.etch.samsungds.net
TLS_HOST=sso.etch.samsungds.net
```

```bash
# 공용 SAN 인증서. 예: Headlamp는 TLS_HOST=headlamp.etch.samsungds.net
CERT_SITE=etch.samsungds.net
read -r -p '등록할 공개 host: ' TLS_HOST
```

추출 때와 다른 터미널에서도 실행할 수 있도록 경로를 다시 설정하고, `kubectl config get-contexts`의 **NAME 열**에서 대상 context를 입력합니다.
이후 명령은 같은 터미널에서 실행합니다.

```bash
CERT_SITE_DIR="$PWD/deploy/shared/certs/$CERT_SITE"
CERT_CA_DIR="$PWD/deploy/shared/certs/ca"
set -o pipefail
kubectl config get-contexts
read -r -p '대상 context 이름: ' KUBE_CONTEXT
export KUBE_CONTEXT
printf '도메인: %s\ncontext: %s\n' "$TLS_HOST" "$KUBE_CONTEXT"
ls -l "$CERT_SITE_DIR/fullchain.crt" "$CERT_SITE_DIR/private.key"
```

**기대 결과:** 적용하려는 도메인·클러스터와 결과 파일 2개가 표시됩니다.
**실패 확인:** 다른 대상이 표시되면 이 단계의 값을 다시 설정합니다.

## 2. 공용 TLS Secret 등록·갱신 — CP1

인증서 파일로 등록합니다.

```bash
make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST="$TLS_HOST" \
  TLS_CERT_FILE="$CERT_SITE_DIR/fullchain.crt" TLS_KEY_FILE="$CERT_SITE_DIR/private.key"
```

기존 `kubernetes.io/tls` Secret(`tls.crt`·`tls.key` 포함)에서 가져올 때는 파일 대신 `TLS_SOURCE=<namespace>/<secret>`을 지정합니다. 원본 Secret은 변경하지 않습니다.

```bash
read -r -p '원본 TLS Secret(namespace/secret): ' TLS_SOURCE
make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST="$TLS_HOST" TLS_SOURCE="$TLS_SOURCE"
```

- 도구가 도메인·만료·인증서와 개인키 일치를 검사하고 다른 도메인의 인증서와 Secret metadata를 보존합니다.
- 동시 변경이 감지되면 덮어쓰지 않고 실패합니다.
- Traefik이 이미 있으면 인증서를 다시 읽도록 재시작하고 rollout 완료를 기다립니다. 갱신을 위해 앱이나 `ingress-up`을 다시 배포할 필요는 없습니다.
- Traefik이 아직 없으면 [Traefik 셋업](../ingress/setup.md)의 3단계로 설치합니다.

**기대 결과:** `공용 TLS 등록 완료: <host>`가 표시됩니다.
**실패 확인:** `공용 TLS 처리 실패`는 인증서·개인키·클러스터 권한·동시 변경을 확인합니다. 메시지에 민감값은 표시되지 않습니다.

## 3. 실제 제공 인증서 확인 — CP1

서비스가 배포되어 있고 CP1에서 대상 IP의 443에 접속할 수 있을 때 실행합니다.
DNS 대신 지정한 IP에 SNI로 접속하므로 DNS 전환 전에도 확인할 수 있습니다. 주소는 [네트워크 원본](../infrastructure/network.md#vipdns접속-경로)의 APP VIP 또는 Traefik Worker IP를 사용합니다.
파일의 서버 인증서와 실제 제공 인증서의 SHA-256 지문을 비교하며, CA가 DER일 수도 있으므로 임시 PEM으로 변환합니다.

```bash
read -r -p '접속할 APP VIP 또는 Worker IP: ' CHECK_IP
(
  set -euo pipefail
  cert_work=$(mktemp -d "$CERT_SITE_DIR/.live-check.XXXXXX")
  trap 'rm -rf "$cert_work"' EXIT
  if ! openssl x509 -inform PEM -in "$CERT_CA_DIR/SECDS-T2RootCA.crt" \
    -out "$cert_work/root.pem" 2>/dev/null; then
    openssl x509 -inform DER -in "$CERT_CA_DIR/SECDS-T2RootCA.crt" -out "$cert_work/root.pem"
  fi
  openssl s_client -connect "$CHECK_IP:443" -servername "$TLS_HOST" \
    -verify_hostname "$TLS_HOST" -verify_return_error -CAfile "$cert_work/root.pem" \
    -showcerts </dev/null > "$cert_work/live-chain.pem"
  openssl x509 -in "$CERT_SITE_DIR/fullchain.crt" \
    -noout -fingerprint -sha256 > "$cert_work/expected.txt"
  openssl x509 -in "$cert_work/live-chain.pem" \
    -noout -fingerprint -sha256 > "$cert_work/actual.txt"
  cmp "$cert_work/expected.txt" "$cert_work/actual.txt"
  echo 'HTTPS 체인·도메인 검증 및 서버 인증서 일치 확인 완료'
)
```

`TLS_SOURCE`로 등록했다면 `expected.txt` 대신 원본 Secret의 `tls.crt` 지문과 비교합니다.

**기대 결과:** `HTTPS 체인·도메인 검증 및 서버 인증서 일치 확인 완료`가 표시됩니다. 이후 DNS가 전환된 도메인은 브라우저에서도 확인합니다.
**실패 확인:** 지문이 다르면 Traefik rollout 완료·대상 IP·공용 TLS 등록과 Traefik 마운트를 확인합니다. 그 밖의 오류는 [문제 해결](#문제-해결)을 봅니다.

## 4. 이전 인증서로 복구

앞서 보관한 유효한 인증서·개인키 쌍(추출 시 `<사이트>/backups/`)을 2단계의 `TLS_CERT_FILE`·`TLS_KEY_FILE`에 지정해 다시 등록하고 3단계로 확인합니다.
원본 PFX 파일은 계속 보관합니다.

## 5. 앱별 후속 작업

- 최초 배포: 공용 인증서를 등록한 뒤 각 앱의 배포 문서를 진행합니다. Keycloak은 [배포](../../../keycloak/docs/02-deploy.md)입니다.
- Headlamp TLS와 Keycloak 로그인용 CA 묶음(`keycloak-ca-bundle.pem`, `headlamp-oidc-ca` ConfigMap): [Headlamp 준비](../../../headlamp/docs/01-prepare.md).
- API server의 OIDC CA: [API server OIDC 인증](../kubernetes/oidc.md). CA를 교체하면 앱과 모든 API server의 신뢰 설정을 함께 갱신합니다. CA가 그대로인 서버 인증서 갱신은 기존 CA 설정을 사용합니다.
- 사용자 PC·노드의 신뢰: 아래 [클라이언트 PC 신뢰 등록](#클라이언트-pc-신뢰-등록).

## 클라이언트 PC 신뢰 등록

서버는 중간 CA를 포함한 fullchain을 제공하고, 접속하는 PC·서버는 루트 CA를 신뢰해야 합니다.
CP1의 신뢰 설정은 PC·앱 Pod·Kubernetes API server에 자동으로 전달되지 않습니다. 앱 Pod와 API server의 신뢰는 위 5단계의 문서를 따릅니다.

### Ubuntu 서버·클라이언트

해당 호스트가 HTTPS 클라이언트로 요청할 때 기본 신뢰 검증이 실패하는 경우에만 진행합니다. 신뢰가 필요한 CP1·Worker 각각에서 수행하며, Root CA 공개 인증서만 전달합니다.

```bash
read -r -p '확인할 공개 도메인: ' TRUST_HOST
curl -v "https://$TRUST_HOST/" -o /dev/null
```

`--cacert`를 지정하면 성공하고 위 요청은 신뢰 오류로 실패하면 Root CA를 등록합니다. PEM 형식의 `.crt` 파일을 사용합니다.

```bash
sudo install -m 0644 deploy/shared/certs/ca/SECDS-T2RootCA.crt \
  /usr/local/share/ca-certificates/SECDS-T2RootCA.crt
sudo update-ca-certificates
curl -v "https://$TRUST_HOST/" -o /dev/null
```

**기대 결과:** 두 번째 `curl`이 신뢰 오류 없이 연결됩니다.
**실패 확인:** 호스트 OS의 신뢰 설정은 컨테이너나 별도 Java/Python 신뢰 저장소에 자동 적용되지 않을 수 있습니다. Pod 내부에서만 실패하면 해당 앱의 신뢰 저장소를 확인합니다.

### Windows 브라우저

서비스 도메인으로 접속합니다. IP SAN이 없는 인증서에 IP 주소로 접속하면 이름 불일치 경고가 발생할 수 있습니다.
인증서 저장소는 현재 사용자 `Win + R` → `certmgr.msc`, 로컬 컴퓨터 `Win + R` → `certlm.msc`에서 확인합니다.

| 저장소 | 확인할 인증서 |
| --- | --- |
| 신뢰할 수 있는 루트 인증 기관 → 인증서 | `SECDS-T2RootCA` |
| 중간 인증 기관 → 인증서 | 필요 시 `SECDS-T2IssuingCA` |

서버가 중간 CA를 제공하면 PC에 중간 인증서를 따로 설치하지 않아도 됩니다.
Root CA가 없다면 회사 인증서 배포 정책에 따라 설치하고 관리 PC의 GPO 배포 여부도 확인합니다.

### 브라우저 오류 확인

서버 검증만으로 브라우저 경고 원인을 단정하지 말고 오류 코드와 실제 표시 인증서를 확인합니다.

| 증상 | 확인 항목 |
| --- | --- |
| `NET::ERR_CERT_AUTHORITY_INVALID` | Root CA 신뢰, 중간 CA 누락, 보안 프록시 인증서 |
| `NET::ERR_CERT_COMMON_NAME_INVALID` | URL과 SAN, IP 접속, 기본 인증서 노출 |
| `NET::ERR_CERT_DATE_INVALID` | 유효기간, PC·서버 시간 |
| Traefik 기본 인증서 표시 | Ingress 도메인·공용 인증서 등록과 마운트, 실제 endpoint |
| 직접 IP 검증 성공, 브라우저만 실패 | PC DNS·LB·프록시 경로, 실제 인증서, 신뢰 정책 |

## 문제 해결

| 표시된 오류 또는 상황 | 먼저 확인할 내용 |
| --- | --- |
| `kubectl` 인증 또는 권한 오류 | 1단계에서 선택한 context와 해당 계정의 접근 권한 |
| `TLS_SOURCE는 namespace/secret 형식` / `tls.crt·tls.key가 필요` | 원본 Secret 이름과 `kubernetes.io/tls` 타입 |
| HTTPS 연결 실패 | 대상 IP의 443 연결, 서비스·Ingress 배포 상태 |
| 3단계 `cmp`에서 파일이 다르다고 표시됨 | 실제 서버가 제공하는 인증서, Traefik 재시작 완료 |
| 3단계 검증 실패 | `TLS_HOST`가 SAN에 있는지, 체인과 루트 CA 원본 |
