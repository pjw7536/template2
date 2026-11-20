# 인증서 서버 적용과 갱신

[가이드 홈](../README.md#https인증서) · 이전: [추출·검증](extract.md) · [원본 준비](prepare.md) · [공용 TLS 등록](../../../README.md#공용-tls-등록)

**목적:** 검증한 인증서가 공용 Traefik의 `etch-sso/traefik-tls` Secret에 등록된 뒤 실제로 제공되는지 확인하고, 갱신·복구와 CA 신뢰를 다룹니다.
등록 명령의 원본은 [공용 TLS 등록](../../../README.md#공용-tls-등록)이며 이 문서는 그 절에 없는 내용만 둡니다.
**준비물:** [추출·검증](extract.md)에 성공한 `fullchain.crt`·`private.key` 또는 기존 `kubernetes.io/tls` Secret, 대상 클러스터 context와 TLS Secret 등록 권한.
**실행 위치:** 관리 호스트의 저장소 루트에서 Bash. 폴더에 파일을 넣는 것만으로 서버 인증서나 Secret은 바뀌지 않습니다.

- 모든 앱은 같은 공용 Secret을 사용하며 Ingress에는 Secret 이름을 지정하지 않습니다. 인증서를 앱 namespace에 복제하지 않습니다.
- 하나의 SAN 인증서가 여러 host를 포함해도 host별로 등록하고 확인합니다.
- 공개 host 목록은 [서비스 원본](../infrastructure/services.md#공개-도메인과-인증)을 따릅니다.

## 1. 적용할 사이트와 대상 클러스터 선택

블록마다 새 셸이므로 아래 값을 각 명령의 자리표시에 직접 씁니다.

| 자리표시 | 값 |
| --- | --- |
| `<사이트>` | 인증서 원본 폴더. 별도 SSO 인증서는 `sso.etch.samsungds.net`, 공용 SAN 인증서는 `etch.samsungds.net` |
| `<공개 host>` | SAN에 포함되어야 하는 실제 공개 host. SSO는 `sso.etch.samsungds.net`, 공용 SAN 인증서는 앱의 host(예: Headlamp는 `headlamp.etch.samsungds.net`) |
| `<context>` | `kubectl config get-contexts`의 `NAME` 열에 있는 대상 context |

[조회] 인증서 파일의 대상·만료와 현재 등록된 host를 확인합니다.

```bash
kubectl config get-contexts
ls -l deploy/shared/certs/<사이트>/fullchain.crt deploy/shared/certs/<사이트>/private.key
openssl x509 -in deploy/shared/certs/<사이트>/fullchain.crt -noout -subject -enddate -ext subjectAltName
kubectl --context "<context>" -n etch-sso describe secret traefik-tls
```

**기대 결과:** 결과 파일 2개, 인증서의 만료일과 SAN, Secret의 `Data` 목록이 표시됩니다. `Data`의 `<host>.crt`·`<host>.key` 쌍이 등록된 host이며 값은 출력되지 않습니다.
**실패 확인:** SAN에 `<공개 host>`가 없으면 그 인증서로는 등록할 수 없습니다. [인증서 발급](../infrastructure/access.md#인증서-발급) 절의 방법으로 SAN을 포함한 인증서를 받습니다. Secret이 `NotFound`면 아직 등록된 인증서가 없는 상태입니다.

## 2. 공용 TLS Secret 등록·갱신 — 관리 호스트

- **처음 등록:** 그 host를 쓰는 앱의 `make ops-deploy`가 준비 검사에서 자동으로 등록합니다. 직접 등록하는 명령은 [공용 TLS 등록](../../../README.md#공용-tls-등록)에 있습니다.
- **갱신:** 준비 검사는 이미 등록된 host를 다시 등록하지 않습니다. 인증서를 새로 추출했으면 그 인증서를 쓰는 host마다 [공용 TLS 등록](../../../README.md#공용-tls-등록)의 `make ingress-tls-up`을 직접 실행한 뒤 3단계로 확인합니다. 대상 host는 1단계의 `Data` 목록에서 찾습니다.
- **기존 Secret에서 가져오기:** 아래 `TLS_SOURCE` 방식을 씁니다.

[변경] 기존 `kubernetes.io/tls` Secret(`tls.crt`·`tls.key` 포함)에서 가져올 때는 파일 대신 `TLS_SOURCE=<namespace>/<secret>`을 지정합니다. 원본 Secret은 변경하지 않습니다.

```bash
make ingress-tls-up KUBE_CONTEXT="<context>" TLS_HOST=<공개 host> TLS_SOURCE=<namespace>/<secret>
```

- 도구가 도메인·만료·인증서와 개인키 일치를 검사하고 다른 도메인의 인증서와 Secret metadata를 보존합니다.
- 동시 변경이 감지되면 덮어쓰지 않고 실패합니다.
- Traefik이 이미 있으면 인증서를 다시 읽도록 재시작하고 rollout 완료를 기다립니다. 갱신을 위해 앱이나 `ingress-up`을 다시 배포할 필요는 없습니다.
- Traefik이 아직 없으면 [ingress 가이드](../../ingress/README.md)로 설치합니다.

**기대 결과:** `공용 TLS 등록 완료: <host>`가 표시됩니다.
**실패 확인:** `공용 TLS 처리 실패`는 인증서·개인키·클러스터 권한·동시 변경을 확인합니다. 메시지에 민감값은 표시되지 않습니다.

## 3. 실제 제공 인증서 확인 — 관리 호스트

서비스가 배포되어 있고 관리 호스트에서 대상 주소의 443에 접속할 수 있을 때 실행합니다.
DNS 대신 지정한 주소에 SNI로 접속하므로 DNS 전환 전에도 확인할 수 있습니다. `<접속 주소>`는 [별칭 표](../infrastructure/aliases.json)의 `VIP-APP` 또는 Traefik Worker의 주소([네트워크 원본](../infrastructure/network.md#vipdns접속-경로))입니다.
파일의 서버 인증서와 실제 제공 인증서의 SHA-256 지문을 비교하며, CA가 DER일 수도 있으므로 임시 PEM으로 변환합니다.

[검사] `<사이트>`·`<공개 host>`·`<접속 주소>`를 바꿔 블록 전체를 실행합니다. 임시 폴더만 쓰고 지우며 클러스터를 바꾸지 않습니다.

```bash
(
  set -euo pipefail
  CERT_SITE=<사이트>
  TLS_HOST=<공개 host>
  CHECK_IP=<접속 주소>
  CERT_SITE_DIR="$PWD/deploy/shared/certs/$CERT_SITE"
  CERT_CA_DIR="$PWD/deploy/shared/certs/ca"
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

**기대 결과:** `HTTPS 체인·도메인 검증 및 서버 인증서 일치 확인 완료`가 표시됩니다. DNS가 등록된 host는 `make <app>-smoke KUBE_CONTEXT="<context>"`의 http 줄로도 체인과 host 검증을 확인합니다.
**실패 확인:** 지문이 다르면 Traefik rollout 완료·대상 주소·공용 TLS 등록과 Traefik 마운트를 확인합니다. 그 밖의 오류는 [문제 해결](#문제-해결)을 봅니다.

[조회] `TLS_SOURCE`로 등록했다면 파일 대신 원본 Secret의 `tls.crt` 지문을 구해, 같은 주소가 제공하는 인증서의 지문과 비교합니다. 두 줄이 같아야 합니다.

```bash
kubectl --context "<context>" -n <namespace> get secret <secret> -o jsonpath='{.data.tls\.crt}' |
  base64 -d | openssl x509 -noout -fingerprint -sha256
openssl s_client -connect "<접속 주소>:443" -servername "<공개 host>" </dev/null 2>/dev/null |
  openssl x509 -noout -fingerprint -sha256
```

## 4. 이전 인증서로 복구

앞서 보관한 유효한 인증서·개인키 쌍(추출 시 `<사이트>/backups/` 아래의 보관 폴더)을 다시 등록하고 3단계로 확인합니다. 원본 PFX 파일은 계속 보관합니다.

[조회] 보관 폴더를 최신순으로 봅니다. `<보관 폴더>`는 되돌릴 시점의 `before-extract.…` 이름입니다.

```bash
ls -1t deploy/shared/certs/<사이트>/backups/
```

[변경] 그 쌍을 host마다 다시 등록합니다.

```bash
make ingress-tls-up KUBE_CONTEXT="<context>" TLS_HOST=<공개 host> TLS_CERT_FILE="$PWD/deploy/shared/certs/<사이트>/backups/<보관 폴더>/fullchain.crt" TLS_KEY_FILE="$PWD/deploy/shared/certs/<사이트>/backups/<보관 폴더>/private.key"
```

성공: `공용 TLS 등록 완료: <host>`. 보관한 인증서가 만료됐으면 도구가 등록을 거부합니다.

## 5. 앱별 후속 작업

- 최초 배포: 각 앱 가이드의 `make ops-deploy`가 공용 인증서 등록까지 수행합니다. Keycloak은 [Keycloak 가이드](../../../keycloak/README.md)입니다.
- Keycloak OIDC를 검증하는 앱(Airflow·Headlamp)의 CA 묶음(`keycloak-ca-bundle.pem`): [사내 CA 묶음](../../../README.md#사내-ca-묶음). CA를 교체하면 묶음을 다시 만들고 그 절에 적힌 앱 쪽 갱신을 수행합니다.
- API server의 OIDC CA: [API server OIDC 인증](../kubernetes/oidc.md#ca-교체). CA를 교체하면 앱과 모든 API server의 신뢰 설정을 함께 갱신합니다. CA가 그대로인 서버 인증서 갱신은 기존 CA 설정을 사용합니다.
- 사용자 PC·노드의 신뢰: 아래 [클라이언트 PC 신뢰 등록](#클라이언트-pc-신뢰-등록).

## 클라이언트 PC 신뢰 등록

서버는 중간 CA를 포함한 fullchain을 제공하고, 접속하는 PC·서버는 루트 CA를 신뢰해야 합니다.
관리 호스트의 신뢰 설정은 PC·앱 Pod·Kubernetes API server에 자동으로 전달되지 않습니다. 앱 Pod와 API server의 신뢰는 위 5단계의 문서를 따릅니다.

### Ubuntu 서버·클라이언트

해당 호스트가 HTTPS 클라이언트로 요청할 때 기본 신뢰 검증이 실패하는 경우에만 진행합니다. 신뢰가 필요한 관리 호스트·Worker 각각에서 수행하며, Root CA 공개 인증서만 전달합니다.
관리 호스트에서는 [관리 호스트 sudo](../infrastructure/access.md#관리-호스트-sudo), Worker에서는 [노드 SSH](../infrastructure/access.md#노드-ssh)의 방법으로 실행합니다.

[조회] 그 호스트에서 현재 신뢰 상태를 확인합니다.

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "https://<공개 host>/"
```

HTTP 상태 코드가 출력되면 이미 신뢰하고 있으므로 아래를 진행하지 않습니다. `SSL certificate problem`으로 실패하면 Root CA를 등록합니다.

[변경] Root CA를 그 호스트의 시스템 신뢰 저장소에 등록합니다. `<Root CA 파일>`은 관리 호스트에서는 `deploy/shared/certs/ca/SECDS-T2RootCA.crt`이고, Worker에서는 그 파일을 [노드 SSH](../infrastructure/access.md#노드-ssh)의 파일 전송 방법으로 복사해 둔 경로(예: `/tmp/SECDS-T2RootCA.crt`)입니다. 첫 줄은 PEM이 아닌 DER 파일도 PEM으로 바꿔 설치합니다.

```bash
openssl x509 -in "<Root CA 파일>" -out /tmp/SECDS-T2RootCA.pem 2>/dev/null ||
  openssl x509 -inform DER -in "<Root CA 파일>" -out /tmp/SECDS-T2RootCA.pem
sudo install -m 0644 /tmp/SECDS-T2RootCA.pem /usr/local/share/ca-certificates/SECDS-T2RootCA.crt
sudo update-ca-certificates
curl -sS -o /dev/null -w '%{http_code}\n' "https://<공개 host>/"
```

**기대 결과:** `update-ca-certificates`가 `1 added`(이미 등록돼 있으면 `0 added`)를 출력하고 마지막 `curl`이 신뢰 오류 없이 HTTP 상태 코드를 출력합니다.
**실패 확인:** 호스트 OS의 신뢰 설정은 컨테이너나 별도 Java/Python 신뢰 저장소에 자동 적용되지 않을 수 있습니다. Pod 내부에서만 실패하면 해당 앱의 신뢰 저장소를 확인합니다.
이미 실행 중인 containerd는 다시 시작해야 새 CA를 읽습니다. 서비스 중인 노드의 containerd 재시작은 [승인] 단계이며 [노드와 관리 호스트의 CA 신뢰](../../../registry/docs/01-operations.md#노드와-관리-호스트의-ca-신뢰)를 따릅니다.

### Windows 브라우저

서비스 도메인으로 접속합니다. IP SAN이 없는 인증서에 IP 주소로 접속하면 이름 불일치 경고가 발생할 수 있습니다.
인증서 저장소는 현재 사용자 `Win + R` → `certmgr.msc`, 로컬 컴퓨터 `Win + R` → `certlm.msc`에서 확인합니다.

| 저장소 | 확인할 인증서 |
| --- | --- |
| 신뢰할 수 있는 루트 인증 기관 → 인증서 | `SECDS-T2RootCA` |
| 중간 인증 기관 → 인증서 | 필요 시 `SECDS-T2IssuingCA` |

서버가 중간 CA를 제공하면 PC에 중간 인증서를 따로 설치하지 않아도 됩니다.
Root CA가 없다면 회사 인증서 배포 정책에 따라 설치하고 관리 PC의 GPO 배포 여부도 확인합니다.
사용자 PC의 화면 확인은 [화면 기능 확인](../infrastructure/access.md#화면-기능-확인) 절을 따릅니다.

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
| `kubectl` 인증 또는 권한 오류 | 1단계에서 선택한 context와 [Kubernetes API](../infrastructure/access.md#kubernetes-api) 절의 접근 방법 |
| `TLS_SOURCE는 namespace/secret 형식` / `tls.crt·tls.key가 필요` | 원본 Secret 이름과 `kubernetes.io/tls` 타입 |
| `인증서와 공개 도메인이 다릅니다` | `<공개 host>`가 인증서의 SAN에 있는지(1단계의 `subjectAltName`) |
| HTTPS 연결 실패 | 대상 주소의 443 연결, 서비스·Ingress 배포 상태 |
| 3단계 `cmp`에서 파일이 다르다고 표시됨 | 실제 서버가 제공하는 인증서, Traefik 재시작 완료 |
| 3단계 검증 실패 | `<공개 host>`가 SAN에 있는지, 체인과 루트 CA 원본 |
