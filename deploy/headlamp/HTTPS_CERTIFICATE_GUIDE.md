# Headlamp HTTPS 인증서 추출·등록·배포 가이드

[Headlamp 운영 안내](README.md) · [APP VIP Worker 구성](../shared/ingress/ADD_WORKER.md)

목표 주소는 **https://etch.samsungds.net/headlamp/** 입니다.
아래 명령은 별도 표시가 없으면 **CP1의 같은 Bash 터미널**에서 순서대로 실행합니다.
각 단계가 실패하면 다음 단계로 넘어가지 말고 해당 오류부터 해결합니다.

```text
내 PC → etch.samsungds.net → APP VIP 10.172.26.150:443
     → Worker의 Traefik → Headlamp Service → Headlamp Pod
```

CP1은 관리 명령과 인증서 등록을 수행합니다. 원본 인증서·개인키를 Worker마다 복사하거나
`/appdata/certs`를 Pod에 마운트하지 않습니다. HTTPS 종료는 Traefik이 담당합니다.

| 항목 | 이번 작업의 값 |
| --- | --- |
| 인증서 도메인 | `etch.samsungds.net` |
| 원본 파일 위치 | CP1 `/appdata/certs` |
| 앱·TLS Secret namespace | `headlamp` |
| TLS Secret 이름 | `headlamp-tls` |
| Traefik Deployment | `etch-sso/traefik` |
| 기존 Keycloak | `etch-sso.samsungds.net`, `etch-sso/keycloak-tls` — 변경하지 않음 |

## 1. 파일·도구·클러스터 확인

필수 원본은 다음 두 파일입니다.

```text
/appdata/certs/etch.samsungds.net.pfx
/appdata/certs/etch.samsungds.net.p7b
```

기존 CA 파일이 있으면 사용하되, 이번 서버 인증서의 발급 체인과 일치하는지 5단계에서 검증합니다.

```text
/appdata/certs/SECDS-T2IssuingCA.crt
/appdata/certs/SECDS-T2RootCA.crt
```

PFX 비밀번호도 준비합니다. 비밀번호는 OpenSSL 입력창에만 입력하며 명령 인자·Git·대화에 남기지 않습니다.
PFX에 개인키가 없다면 발급 담당자에게 짝인 개인키가 포함된 PFX를 요청합니다.

```bash
openssl version
kubectl version --client
helm version --short
python3 --version
kubectl config get-contexts
read -r -p '배포할 context 이름: ' KUBE_CONTEXT
export KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
kubectl --context "$KUBE_CONTEXT" -n etch-sso get deployment traefik

ls -l /appdata/certs/etch.samsungds.net.pfx /appdata/certs/etch.samsungds.net.p7b
```

Python 3.10+, Helm 3, kubectl, OpenSSL이 필요합니다. 현재 계정은 인증서 폴더 읽기·쓰기와
Headlamp 배포·RBAC 관리·Traefik Deployment patch 권한이 있어야 합니다.
APP VIP의 Worker 구성은 이미 완료됐다는 전제입니다. 미완료라면 위 Worker 구성 문서를 먼저 따릅니다.

## 2. 이번 작업용 폴더 만들기

기존 Keycloak 파일과 이전 추출 결과를 덮어쓰지 않도록 새 폴더를 만듭니다.
이 폴더는 Git 저장소 밖이며 개인키가 저장됩니다. 기존 `/appdata/certs` 전체의 소유권·권한은 바꾸지 않습니다.

```bash
set -o pipefail
umask 077
export TLS_WORKDIR="$(mktemp -d /appdata/certs/etch-headlamp.XXXXXX)"
printf '이번 인증서 작업 폴더: %s\n' "$TLS_WORKDIR"
chmod 600 /appdata/certs/etch.samsungds.net.pfx
```

출력된 경로를 기록합니다. 터미널을 다시 열면 `TLS_WORKDIR`와 `KUBE_CONTEXT`를 같은 값으로 다시 설정합니다.
권한 오류가 나면 파일 소유자·관리자에게 접근 권한을 요청하며 `chmod 777`로 해결하지 않습니다.

## 3. PFX에서 서버 인증서와 개인키 추출

### 3-1. 서버 인증서

```bash
openssl pkcs12 \
  -in /appdata/certs/etch.samsungds.net.pfx \
  -clcerts -nokeys \
  -out "$TLS_WORKDIR/etch-leaf-bag.pem"

openssl x509 \
  -in "$TLS_WORKDIR/etch-leaf-bag.pem" \
  -out "$TLS_WORKDIR/etch-leaf.pem"
```

첫 명령의 `Import Password`에 PFX 비밀번호를 입력합니다.
일반적인 단일 서버 인증서 PFX 기준입니다. 여러 서버 인증서·개인키가 들어 있다면
발급 담당자에게 이번 도메인의 한 쌍으로 내보낸 PFX를 요청합니다.

### 3-2. 개인키

```bash
openssl pkcs12 \
  -in /appdata/certs/etch.samsungds.net.pfx \
  -nocerts -nodes \
  -out "$TLS_WORKDIR/etch-key-bag.pem"

openssl pkey \
  -in "$TLS_WORKDIR/etch-key-bag.pem" \
  -out "$TLS_WORKDIR/etch-privkey.pem"

chmod 600 "$TLS_WORKDIR/etch-key-bag.pem" "$TLS_WORKDIR/etch-privkey.pem"
openssl pkey -in "$TLS_WORKDIR/etch-privkey.pem" -check -noout
```

`-nodes`는 Kubernetes에 등록할 암호화되지 않은 PEM 개인키를 추출하는 옵션입니다.
작업 폴더와 개인키 파일은 현재 계정만 접근할 수 있게 유지합니다. 개인키를 `cat`으로 출력하지 않습니다.

OpenSSL 3에서 RC2 등 옛 암호 관련 `unsupported` 오류가 나면 실패한 `openssl pkcs12` 명령에만
`-legacy`를 추가해 재실행합니다. 비밀번호 오류에는 해당하지 않습니다.
이 옵션으로도 해결되지 않으면 담당자에게 최신 암호 방식으로 PFX 재생성을 요청합니다.

## 4. 중간 CA와 Root CA 준비

### 4-A. 기존 두 CA 파일이 있는 경우 — 기본 경로

PEM이면 그대로 정규화하고, DER이면 PEM으로 변환합니다. 원본은 수정하지 않습니다.

```bash
openssl x509 -inform PEM -in /appdata/certs/SECDS-T2IssuingCA.crt \
  -out "$TLS_WORKDIR/issuing-ca.pem" 2>/dev/null || \
openssl x509 -inform DER -in /appdata/certs/SECDS-T2IssuingCA.crt \
  -out "$TLS_WORKDIR/issuing-ca.pem"

openssl x509 -inform PEM -in /appdata/certs/SECDS-T2RootCA.crt \
  -out "$TLS_WORKDIR/root-ca.pem" 2>/dev/null || \
openssl x509 -inform DER -in /appdata/certs/SECDS-T2RootCA.crt \
  -out "$TLS_WORKDIR/root-ca.pem"
```

각 원본 CA 파일이 단일 인증서인 경우의 명령입니다. 성공하면 5단계로 갑니다.

### 4-B. CA 파일이 없거나 이번 발급 체인과 다른 경우

PFX의 CA 인증서와 P7B 내용을 별도로 추출해 확인합니다.

```bash
openssl pkcs12 \
  -in /appdata/certs/etch.samsungds.net.pfx \
  -cacerts -nokeys -out "$TLS_WORKDIR/pfx-ca-bundle.pem"

openssl pkcs7 -inform PEM -in /appdata/certs/etch.samsungds.net.p7b \
  -print_certs -out "$TLS_WORKDIR/p7b-certificates.pem" 2>/dev/null || \
openssl pkcs7 -inform DER -in /appdata/certs/etch.samsungds.net.p7b \
  -print_certs -out "$TLS_WORKDIR/p7b-certificates.pem"

openssl crl2pkcs7 -nocrl -certfile "$TLS_WORKDIR/p7b-certificates.pem" | \
  openssl pkcs7 -print_certs -noout
```

P7B에는 서버 인증서도 섞여 있을 수 있으므로 전체를 leaf 뒤에 그대로 붙이지 않습니다.
개별 인증서를 파일로 분리해 subject·issuer·CA 여부·지문을 확인할 수 있습니다.

```bash
python3 - <<'PY'
import os
import re
from pathlib import Path
work = Path(os.environ['TLS_WORKDIR'])
for source in ('pfx-ca-bundle', 'p7b-certificates'):
    text = (work / f'{source}.pem').read_text()
    certs = re.findall(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', text, re.S)
    for index, cert in enumerate(certs, 1):
        (work / f'{source}-{index}.pem').write_text(cert + '\n')
    print(source, '인증서 수:', len(certs))
PY

for cert in "$TLS_WORKDIR"/pfx-ca-bundle-[0-9]*.pem "$TLS_WORKDIR"/p7b-certificates-[0-9]*.pem; do
  [ -f "$cert" ] || continue
  printf '\n파일: %s\n' "$cert"
  openssl x509 -in "$cert" -noout -subject -issuer -fingerprint -sha256 -ext basicConstraints
done
```

발급 담당자의 CA 지문·체인 정보와 대조해 확인한 중간 CA를 `issuing-ca.pem`, Root CA를
`root-ca.pem`으로 작업 폴더에 준비한 뒤 진행합니다. 파일 순번만 보고 고르지 않습니다.
Root CA가 번들에 없으면 사내 공식 배포처에서 받습니다. 추출한 인증서를 확인 없이 신뢰 저장소에 설치하지 않습니다.
중간 CA가 여러 개라면 서버 인증서 발급자부터 상위 중간 CA 순서로 `issuing-ca.pem`에 연결합니다.
Root CA와 서버 인증서는 `issuing-ca.pem`에 넣지 않습니다.

## 5. 도메인·개인키·체인 검증

### 5-1. 서버 인증서 이름과 유효기간

```bash
openssl x509 -in "$TLS_WORKDIR/etch-leaf.pem" \
  -noout -subject -issuer -dates -ext subjectAltName
openssl x509 -in "$TLS_WORKDIR/etch-leaf.pem" -noout -checkhost etch.samsungds.net
openssl x509 -in "$TLS_WORKDIR/etch-leaf.pem" -noout -checkend 0
```

SAN이 `etch.samsungds.net`을 포함하거나 유효한 와일드카드로 포함해야 합니다.
파일 이름만으로 도메인을 판단하지 않습니다. `etch-sso.samsungds.net`만 포함하면 이번 용도로 사용할 수 없습니다.

### 5-2. 인증서·개인키의 공개키 일치

```bash
openssl x509 -in "$TLS_WORKDIR/etch-leaf.pem" -pubkey -noout | \
  openssl pkey -pubin -outform DER | openssl dgst -sha256

openssl pkey -in "$TLS_WORKDIR/etch-privkey.pem" -pubout -outform DER | \
  openssl dgst -sha256
```

두 SHA256 값이 정확히 같아야 합니다. 다르면 Secret을 등록하지 않습니다.

### 5-3. 발급 체인·호스트명·서버 용도 확인

```bash
openssl verify -purpose sslserver -verify_hostname etch.samsungds.net \
  -CAfile "$TLS_WORKDIR/root-ca.pem" \
  -untrusted "$TLS_WORKDIR/issuing-ca.pem" \
  "$TLS_WORKDIR/etch-leaf.pem"
```

결과가 `etch-leaf.pem: OK`여야 합니다. 실패하면 만료·발급 체인·중간 CA 누락·이름 불일치를 해결합니다.

## 6. Fullchain 만들기

```bash
cat "$TLS_WORKDIR/etch-leaf.pem" "$TLS_WORKDIR/issuing-ca.pem" \
  > "$TLS_WORKDIR/etch-fullchain.pem"

openssl crl2pkcs7 -nocrl -certfile "$TLS_WORKDIR/etch-fullchain.pem" | \
  openssl pkcs7 -print_certs -noout
```

출력 순서는 **etch 서버 인증서 → 바로 위 중간 CA → 추가 상위 중간 CA(있는 경우)** 입니다.
Root CA는 fullchain에 넣지 않습니다. 인증서 개수는 중간 CA 개수에 따라 다릅니다.
이제 등록에 사용할 두 파일은 다음과 같습니다.

```text
$TLS_WORKDIR/etch-fullchain.pem
$TLS_WORKDIR/etch-privkey.pem
```

## 7. Kubernetes TLS Secret 등록

먼저 namespace를 준비하고 기존 Secret 유무를 확인합니다.

```bash
kubectl --context "$KUBE_CONTEXT" create namespace headlamp --dry-run=client -o yaml | \
  kubectl --context "$KUBE_CONTEXT" apply -f -

kubectl --context "$KUBE_CONTEXT" -n headlamp get secret headlamp-tls --ignore-not-found
```

이미 Secret이 출력되면 갱신 작업입니다. 아래 명령으로 기존 Secret을 제한된 작업 폴더에 백업합니다.
최초 등록으로 출력이 없었다면 백업 명령은 건너뜁니다. 백업에는 개인키가 있으므로 공유하지 않습니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n headlamp get secret headlamp-tls -o json \
  > "$TLS_WORKDIR/headlamp-tls-before.json"
chmod 600 "$TLS_WORKDIR/headlamp-tls-before.json"
```

검증된 인증서를 등록합니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n headlamp create secret tls headlamp-tls \
  --cert="$TLS_WORKDIR/etch-fullchain.pem" \
  --key="$TLS_WORKDIR/etch-privkey.pem" \
  --dry-run=client -o yaml | \
  kubectl --context "$KUBE_CONTEXT" apply -f -

kubectl --context "$KUBE_CONTEXT" -n headlamp get secret headlamp-tls
```

타입이 `kubernetes.io/tls`, DATA가 `2`인지 확인합니다. `etch-sso/keycloak-tls`는 수정하지 않습니다.

## 8. Headlamp 설정·검사·배포

현재 가이드와 HTTPS 지원 코드가 있는 서버 checkout을 사용합니다.
아래 경로는 CP1의 실제 프로젝트 루트로 바꾸며 인증서 폴더에서 `make`를 실행하지 않습니다.

```bash
cd /실제/프로젝트/tailwind
# env 파일이 없을 때만 예시를 복사합니다.
if [ ! -f deploy/headlamp/env/k8s.env ]; then
  cp deploy/headlamp/env/k8s.env.example deploy/headlamp/env/k8s.env
fi
```

`deploy/headlamp/env/k8s.env`의 기존 이미지 미러·인증 설정을 유지하고 아래 키를 설정합니다.
같은 키를 중복해서 넣지 않습니다.

```dotenv
HEADLAMP_HOST=etch.samsungds.net
HEADLAMP_TLS_SECRET=headlamp-tls
```

차트가 이미 준비되었다면 다시 받지 않습니다. 미준비인 경우만 실행합니다.

```bash
make headlamp-fetch-chart
```

검사와 배포는 순서대로 실행하며 실패 시 다음 명령을 실행하지 않습니다.

```bash
make server-check APP=headlamp
make headlamp-check
make headlamp-up KUBE_CONTEXT="$KUBE_CONTEXT"

kubectl --context "$KUBE_CONTEXT" -n headlamp get pods,svc,ingress -o wide
kubectl --context "$KUBE_CONTEXT" -n etch-sso get pods -l app.kubernetes.io/name=traefik -o wide
```

Headlamp Pod가 `1/1 Running`이고 Ingress의 host가 `etch.samsungds.net`이어야 합니다.
배포 도구가 baseURL·probe·Ingress를 `/headlamp`에 맞추고 Traefik의 namespace 감시·권한을 추가합니다.
기존 VIP Worker 배치와 다른 앱의 감시 목록을 보존합니다. 감시 설정 변경 시 Traefik Pod가 교체될 수 있습니다.
별도 StripPrefix 설정과 `make headlamp-ui`는 필요하지 않습니다.

## 9. Worker와 APP VIP에서 HTTPS 검증

먼저 각 Backend와 VIP를 같은 도메인으로 검사합니다. IP 목록은 현재 LB 구성과 맞춰 사용합니다.
`--resolve`는 실제 DNS 변경 전에 SNI·호스트명·경로를 올바르게 검사합니다. `-k`는 사용하지 않습니다.

```bash
for target in 10.172.40.87 10.172.40.117 10.172.26.150; do
  printf '\n검사 대상: %s\n' "$target"
  curl --fail --show-error --connect-timeout 5 --max-time 20 \
    --cacert "$TLS_WORKDIR/root-ca.pem" \
    --resolve "etch.samsungds.net:443:$target" \
    https://etch.samsungds.net/headlamp/ -o /dev/null || break
done
```

세 대상 모두 성공해야 합니다. 첫 실패에서 루프가 멈추므로 출력된 대상 수까지 확인합니다.
서버가 실제 보내는 체인·호스트명을 자세히 확인하려면 다음을 실행합니다.

```bash
openssl s_client \
  -connect 10.172.26.150:443 \
  -servername etch.samsungds.net \
  -verify_hostname etch.samsungds.net \
  -verify_return_error \
  -CAfile "$TLS_WORKDIR/root-ca.pem" \
  -showcerts </dev/null
```

`Verify return code: 0 (ok)`를 확인합니다. 이 결과는 지정한 VIP·CA·도메인의 검증 결과입니다.
각 PC가 실제 같은 endpoint에 접속하는지와 CA를 신뢰하는지는 별도로 확인합니다.
Secret 변경은 Traefik이 감지하므로 무조건 재시작하지 않습니다. 이전 인증서가 계속 보이면
Ingress의 Secret 참조·Traefik namespace 감시·권한·로그를 먼저 확인합니다.

## 10. DNS·PC 신뢰 설정·로그인

DNS 담당자에게 **`etch.samsungds.net → 10.172.26.150`** 연결을 확인합니다.
다른 앱도 같은 도메인을 사용한다면 기존 Ingress와 함께 동작하는지 확인합니다.

```bash
getent hosts etch.samsungds.net
curl --fail --show-error --connect-timeout 5 --max-time 20 \
  --cacert "$TLS_WORKDIR/root-ca.pem" \
  https://etch.samsungds.net/headlamp/ -o /dev/null
```

Windows PC에서는 `nslookup etch.samsungds.net`으로 DNS를 확인합니다.
브라우저가 신뢰하려면 발급 Root CA가 PC의 신뢰할 수 있는 루트 인증 기관에 있어야 합니다.
사내 GPO·인증서 배포 절차를 따릅니다. 서버가 올바른 중간 인증서를 제공하면 PC에 중간 CA를
반드시 수동 설치할 필요는 없습니다. 브라우저 오류가 남으면 실제 표시된 인증서·SAN·만료·DNS·프록시도 확인합니다.

CP1·Worker의 OS 신뢰 등록은 **그 노드 자체에서 HTTPS 클라이언트 요청을 할 때 필요한 경우만** 합니다.
Headlamp 서비스 제공을 위해 모든 Worker에 개인키나 CA를 설치할 필요는 없습니다.
검증한 사내 Root CA를 Ubuntu의 신뢰 저장소에 등록할 경우, 해당 서버에서 다음을 실행합니다.

```bash
sudo install -m 0644 "$TLS_WORKDIR/root-ca.pem" \
  /usr/local/share/ca-certificates/etch-corporate-root.crt
sudo update-ca-certificates
```

이미 같은 CA가 등록되어 있으면 추가하지 않습니다. 다른 노드에는 검증한 Root CA 공개 파일만 전달하며,
이 OS 설정이 Pod나 Java 등의 별도 신뢰 저장소에 자동 반영된다고 가정하지 않습니다.

CP1에서 조회용 토큰을 발급합니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n headlamp create token headlamp-viewer --duration=1h
```

PC 브라우저에서 **https://etch.samsungds.net/headlamp/** 를 열고 토큰을 입력합니다.
정적 파일 로딩·노드 목록·Pod 로그 조회를 확인합니다. 토큰 만료 시 다시 발급합니다.

## 11. 오류 진단·인증서 갱신

| 증상 | 확인할 곳 |
| --- | --- |
| PFX 비밀번호 오류 | 발급 시 설정한 PFX 비밀번호 |
| RC2/unsupported | OpenSSL 3 `pkcs12 -legacy` 또는 PFX 재발급 |
| 공개키 SHA256 불일치 | 서버 인증서와 개인키가 같은 PFX의 쌍인지 |
| unable to get local issuer certificate | 중간 CA 누락·다른 발급 체인 |
| Traefik 기본 인증서 표시 | Ingress host·TLS Secret·감시 namespace·조회 권한 |
| 도메인 불일치 | SAN, SNI, 접속 URL, 실제 제공 인증서 |
| Worker 성공·VIP 실패 | LB Backend·Health Check·방화벽 |
| VIP 성공·PC 실패 | PC DNS·프록시·Root CA 신뢰·브라우저 인증서 |
| 404 | `/headlamp/` 경로·IngressClass·namespace 감시 |
| 503 | Headlamp Pod 준비 상태·Service endpoint |
| Forbidden 로그인 | 토큰 만료·ServiceAccount 및 조회 RBAC |

```bash
kubectl --context "$KUBE_CONTEXT" -n headlamp describe ingress headlamp
kubectl --context "$KUBE_CONTEXT" -n headlamp get endpointslices \
  -l kubernetes.io/service-name=headlamp
kubectl --context "$KUBE_CONTEXT" -n headlamp logs deployment/headlamp --tail=100
kubectl --context "$KUBE_CONTEXT" -n etch-sso logs \
  -l app.kubernetes.io/name=traefik --tail=100 --prefix=true
```

인증서 갱신은 새 작업 폴더에서 추출·검증을 반복한 뒤 동일 Secret을 갱신하고 9~10단계를 재검증합니다.
같은 Traefik에서 `etch.samsungds.net` 인증서를 쓰는 다른 앱 Secret이 있다면 함께 갱신 관리합니다.
이전 정상 Secret 백업이 있고 갱신 후 문제가 생겼다면, 다른 운영자가 이후 갱신하지 않았는지 확인한 후
아래처럼 **TLS 데이터만** 복원합니다. 최초 설치에는 이 복구를 사용하지 않습니다.

```bash
python3 - <<'PY'
import json
import os
from pathlib import Path
work = Path(os.environ['TLS_WORKDIR'])
before = json.loads((work / 'headlamp-tls-before.json').read_text())
(work / 'restore-tls.json').write_text(json.dumps({'data': before['data'], 'type': before['type']}))
PY
kubectl --context "$KUBE_CONTEXT" -n headlamp patch secret headlamp-tls \
  --type=merge --patch-file "$TLS_WORKDIR/restore-tls.json"
```

복원 후 실제 HTTPS 인증서를 다시 검증합니다. 작업 폴더·원본 PFX·개인키·Secret 백업은 사내 비밀정보 보관 정책으로 관리하고 Git에 넣지 않습니다.

## 완료 기준

- [ ] 인증서가 `etch.samsungds.net`에 유효하고 개인키와 일치함
- [ ] 체인·서버 용도·호스트명 검증이 OK임
- [ ] fullchain은 leaf부터 중간 CA 순서이며 Root CA를 포함하지 않음
- [ ] `headlamp/headlamp-tls`에 등록하고 Headlamp 배포가 완료됨
- [ ] 각 Worker와 APP VIP에서 HTTPS 검사 성공
- [ ] 실제 PC DNS·CA 신뢰·로그인·목록·로그 조회 확인

## 공식 참고

- [OpenSSL PKCS12/PFX 추출](https://docs.openssl.org/3.0/man1/openssl-pkcs12/)
- [OpenSSL PKCS7/P7B 읽기](https://docs.openssl.org/3.0/man1/openssl-pkcs7/)
- [OpenSSL 체인 검증](https://docs.openssl.org/3.0/man1/openssl-verify/)
- [OpenSSL HTTPS endpoint 검증](https://docs.openssl.org/3.0/man1/openssl-s_client/)
- [Kubernetes Ingress TLS](https://kubernetes.io/docs/concepts/services-networking/ingress/#tls)
