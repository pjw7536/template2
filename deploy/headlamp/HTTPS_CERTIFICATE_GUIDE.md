# Headlamp HTTPS 인증서 적용 가이드

[Headlamp 운영 안내](README.md)

기존 Keycloak에서 정상 동작한 절차를 Headlamp에 맞춰 적용합니다.
**CP1에서 순서대로 실행하고, 오류가 나면 다음 단계로 넘어가지 않습니다.**

| 항목 | 값 |
| --- | --- |
| 접속 주소 | `https://etch.samsungds.net/headlamp/` |
| 작업 폴더 | `/appdata/certs` |
| TLS Secret | `headlamp/headlamp-tls` |
| TLS 종료 | 기존 `etch-sso/traefik` |
| APP VIP | `10.172.26.150:443` |

## 1. 원본 파일 확인

받은 PFX와 P7B를 CP1의 `/appdata/certs`에 준비합니다.

```text
etch.samsungds.net.pfx
etch.samsungds.net.p7b
```

개별 CA 파일 `SECDS-T2IssuingCA.crt`, `SECDS-T2RootCA.crt`가 이미 있으면
**PEM 형식**인지 확인하고 2단계로 갑니다. 이번 인증서와 맞는지는 3단계에서 검증합니다.
없으면 아래 절차로 P7B/PFX에 포함되어 있는지 확인합니다. 두 형식 모두 CA 체인이
항상 들어 있는 것은 아니며, 파일명만으로 포함 여부나 올바른 발급기관을 판단하지 않습니다.
기존 `keycloak-*` 파일과 `etch-sso/keycloak-tls`는 그대로 둡니다.
이번 절차에서 만드는 `etch-*` 파일이 이미 있다면 먼저 별도로 보관합니다.

```bash
cd /appdata/certs
umask 077
set -o pipefail

kubectl config current-context
export KUBE_CONTEXT="$(kubectl config current-context)"
```

출력된 context가 배포할 클러스터인지 확인합니다.

### 개별 중간·루트 인증서가 없을 때

먼저 P7B에서 공개 인증서 묶음을 추출합니다. PEM 입력으로 성공하면 DER 명령은 생략합니다.

```bash
openssl pkcs7 -inform PEM -in etch.samsungds.net.p7b \
  -print_certs -out etch-p7b-certs.pem
```

PEM 형식 오류라면 DER 입력으로 다시 실행합니다. 이것도 실패하면 파일 형식·손상을 확인합니다.

```bash
openssl pkcs7 -inform DER -in etch.samsungds.net.p7b \
  -print_certs -out etch-p7b-certs.pem
```

P7B가 없거나 필요한 CA가 포함되지 않았다면 PFX에서도 CA 인증서를 추출할 수 있습니다.
비밀번호를 입력하며, `-nokeys`로 개인키는 추출하지 않습니다.

```bash
openssl pkcs12 -in etch.samsungds.net.pfx \
  -cacerts -nokeys -out etch-pfx-ca.pem
```

OpenSSL 3의 구형 암호 알고리즘 `unsupported` 오류에만 `-legacy`를 추가합니다.
명령이 성공해도 CA 인증서가 없으면 추출 결과에 인증서 블록이 없을 수 있습니다.

성공한 추출 파일을 지정해 인증서를 개별 PEM 파일로 나누고 내용을 확인합니다.
PFX 결과를 확인할 때는 `CERT_BUNDLE=etch-pfx-ca.pem`으로 바꿉니다.
실행할 때마다 새 임시 폴더를 만들어 이전 추출 결과가 섞이지 않게 합니다.

```bash
CERT_BUNDLE=etch-p7b-certs.pem
CERT_PARTS_DIR="$(mktemp -d /appdata/certs/etch-ca-parts.XXXXXX)"

awk -v dir="$CERT_PARTS_DIR" '
  /-----BEGIN CERTIFICATE-----/ { n++; out=sprintf("%s/cert-%02d.pem", dir, n) }
  out != "" { print > out }
  /-----END CERTIFICATE-----/ { close(out); out="" }
' "$CERT_BUNDLE"

for cert in "$CERT_PARTS_DIR"/cert-*.pem; do
  [ -f "$cert" ] || continue
  printf '\n%s\n' "$cert"
  openssl x509 -in "$cert" -noout -subject -issuer -dates \
    -fingerprint -sha256 -ext basicConstraints
done
```

- 중간 CA 후보: `CA:TRUE`이며, 2단계에서 추출할 서버 인증서의 issuer와 subject가 연결되는 인증서입니다.
- 루트 CA 후보: 일반적으로 `CA:TRUE`이고 subject와 issuer가 같습니다.
  이것만으로 신뢰하지 말고 사내 인증서 담당자가 제공한 SHA-256 지문과 대조합니다.
- 출력 순서는 체인 순서가 아닐 수 있습니다. 이름이 연결되어도 실제 서명 검증은 3단계에서 해야 합니다.

확인한 인증서를 각각 `SECDS-T2IssuingCA.crt`, `SECDS-T2RootCA.crt`로 복사합니다.
이 이름은 기존 절차의 예시이며 실제 발급기관이 다르면 이후 명령의 파일명도 맞춥니다.
중간 CA가 여러 개라면 서버 인증서의 직접 발급자부터 루트 방향으로 묶어
`SECDS-T2IssuingCA.crt`에 저장합니다. 서버 인증서와 루트는 이 묶음에 넣지 않습니다.

**P7B/PFX에도 필요한 CA가 없다면 로컬 추출만으로 체인을 완성할 수 없습니다.**
사내 인증서 담당자에게 이번 서버 인증서의 **중간 CA 전체 체인과 루트 CA 공개 인증서(PEM),
루트 SHA-256 지문**을 요청합니다. 관리되는 Windows 신뢰 저장소에 같은 루트가 있다면
개인키 없이 Base-64 encoded X.509로 내보내 반입하고 지문을 확인할 수도 있습니다.
서버 인증서만으로 누락된 CA 인증서를 생성할 수는 없습니다.

중간 CA는 서버가 보내는 fullchain 구성에, 루트 CA는 검증과 클라이언트 신뢰 설정에 필요합니다.
루트 파일이 없다는 이유로 fullchain에 임의의 인증서를 추가하거나 검증을 생략하지 않습니다.
필요한 CA를 확보한 후 아래 단계로 진행합니다.

## 2. 서버 인증서와 개인키 추출

각 명령이 요청하면 PFX 비밀번호를 입력합니다.

```bash
openssl pkcs12 \
  -in etch.samsungds.net.pfx \
  -clcerts -nokeys |
openssl x509 -out etch-leaf.crt
```

```bash
openssl pkcs12 \
  -in etch.samsungds.net.pfx \
  -nocerts -nodes |
openssl pkey -out etch.key

chmod 600 etch.key
```

`etch.key`는 개인키이므로 Git이나 대화에 첨부하지 않습니다.
OpenSSL 3에서 구형 암호 알고리즘 `unsupported` 오류가 나면 해당 `openssl pkcs12` 명령에
`-legacy`를 추가합니다. 비밀번호 오류에는 적용하지 않습니다.

## 3. 인증서 검증

### 도메인과 유효기간

```bash
openssl x509 -in etch-leaf.crt \
  -noout -subject -issuer -dates -ext subjectAltName
```

SAN이 `etch.samsungds.net`과 일치하고 현재 시간이 유효기간 안에 있어야 합니다.

### 인증서와 개인키 일치

```bash
openssl x509 -in etch-leaf.crt -pubkey -noout |
openssl pkey -pubin -outform DER |
openssl sha256

openssl pkey -in etch.key -pubout -outform DER |
openssl sha256
```

**두 SHA256 값이 같아야 합니다.**

### CA 체인과 호스트명

```bash
openssl verify \
  -purpose sslserver \
  -verify_hostname etch.samsungds.net \
  -CAfile SECDS-T2RootCA.crt \
  -untrusted SECDS-T2IssuingCA.crt \
  etch-leaf.crt
```

`etch-leaf.crt: OK`이면 다음 단계로 갑니다.
`unable to get local issuer certificate` 또는 `unable to verify the first certificate`는
발급자 체인을 연결하지 못했다는 뜻입니다. CA 누락뿐 아니라 다른 CA 파일을 지정했거나
중간 CA가 더 필요한 경우도 있으므로, 위 추출 결과와 서버 인증서의 issuer를 다시 확인합니다.
CA 파일 자체를 열지 못하는 오류라면 경로·파일 존재 여부·PEM 형식부터 확인합니다.

## 4. Fullchain 생성

서버 인증서 다음에 Intermediate CA를 넣습니다. Root CA는 넣지 않습니다.

```bash
cat etch-leaf.crt SECDS-T2IssuingCA.crt > etch-fullchain.crt

grep -c 'BEGIN CERTIFICATE' etch-fullchain.crt
```

중간 CA가 하나면 `2`, 여러 개면 `1 + 중간 CA 개수`가 나와야 합니다.
개수만으로 체인이 유효하다고 판단하지 않고 3단계의 검증 성공을 전제로 합니다.

## 5. Kubernetes TLS Secret 등록

```bash
kubectl --context "$KUBE_CONTEXT" create namespace headlamp --dry-run=client -o yaml |
kubectl --context "$KUBE_CONTEXT" apply -f -

kubectl --context "$KUBE_CONTEXT" -n headlamp create secret tls headlamp-tls \
  --cert=/appdata/certs/etch-fullchain.crt \
  --key=/appdata/certs/etch.key \
  --dry-run=client -o yaml |
kubectl --context "$KUBE_CONTEXT" apply -f -

kubectl --context "$KUBE_CONTEXT" -n headlamp get secret headlamp-tls
```

`TYPE=kubernetes.io/tls`, `DATA=2`인지 확인합니다.
여기서 DATA는 `tls.crt`, `tls.key` 두 항목을 뜻합니다. Worker에 파일을 복사할 필요는 없습니다.

등록된 인증서 체인도 확인합니다. 개인키는 출력하지 않습니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n headlamp get secret headlamp-tls \
  -o jsonpath='{.data.tls\.crt}' |
base64 -d > /appdata/certs/etch-live-fullchain.crt

openssl crl2pkcs7 -nocrl -certfile /appdata/certs/etch-live-fullchain.crt |
openssl pkcs7 -print_certs -noout
```

출력에 `etch.samsungds.net` 서버 인증서와 해당 Intermediate CA가 순서대로 있어야 합니다.

## 6. Headlamp 배포

[Keycloak 전환 절차](OIDC.md)의 인증 설정과 OIDC env·Secret을 먼저 준비합니다.

**CP1의 프로젝트 루트로 이동합니다.** 아래 경로는 실제 서버 checkout 위치로 바꿉니다.

```bash
cd /실제/프로젝트/tailwind
```

`deploy/headlamp/env/k8s.env`의 기존 이미지 설정은 유지하고 아래 두 값을 설정합니다.
파일이 없다면 `k8s.env.example`을 복사해서 만듭니다. 같은 키를 중복해서 넣지 않습니다.

```dotenv
HEADLAMP_HOST=etch.samsungds.net
HEADLAMP_TLS_SECRET=headlamp-tls
```

Helm·kubectl·Python 3.10+와 chart가 준비된 상태에서 실행합니다.
차트가 없을 때만 `make headlamp-fetch-chart`로 준비합니다.

```bash
make server-check APP=headlamp
make headlamp-check
make headlamp-up KUBE_CONTEXT="$KUBE_CONTEXT"

kubectl --context "$KUBE_CONTEXT" -n headlamp get pods,svc,ingress -o wide
kubectl --context "$KUBE_CONTEXT" -n headlamp get ingress headlamp -o yaml
```

Pod는 `1/1 Running`, Ingress는 다음 값이어야 합니다.

- host: `etch.samsungds.net`
- path: `/headlamp`
- ingressClassName: `traefik`
- TLS Secret: `headlamp-tls`

배포 명령이 Headlamp 경로 설정과 Traefik의 namespace 감시·권한을 연결합니다.
Traefik은 `etch-sso`에 그대로 있고 감시 설정 변경 시 Pod가 교체될 수 있습니다.
인증서 등록만을 이유로 추가 재시작할 필요는 없습니다.

## 7. APP VIP와 도메인 접속 검증

```bash
openssl s_client \
  -connect 10.172.26.150:443 \
  -servername etch.samsungds.net \
  -verify_hostname etch.samsungds.net \
  -verify_return_error \
  -CAfile /appdata/certs/SECDS-T2RootCA.crt \
  -showcerts </dev/null
```

`Verify return code: 0 (ok)`인지 확인합니다.
각 Worker도 확인하려면 `-connect`를 각각 `10.172.40.87:443`, `10.172.40.117:443`으로 바꿔 실행합니다.

DNS는 **`etch.samsungds.net → 10.172.26.150`** 이어야 합니다.

```bash
getent hosts etch.samsungds.net

curl --fail --show-error --connect-timeout 5 --max-time 20 \
  --cacert /appdata/certs/SECDS-T2RootCA.crt \
  https://etch.samsungds.net/headlamp/ -o /dev/null
```

인증서 검증은 성공해도 404/503이면 Ingress 경로·Headlamp Pod·Service 연결을 확인합니다.

## 8. PC 신뢰 설정과 로그인

Windows PC에서 Root CA가 이미 신뢰되어 있다면 추가 작업 없이 접속합니다.
인증서 경고가 나면 `Win + R → certmgr.msc`에서
**신뢰할 수 있는 루트 인증 기관 → SECDS-T2RootCA**를 확인하고 사내 배포 절차로 등록합니다.
CP1에 CA를 설치해도 Windows PC의 신뢰 설정은 바뀌지 않습니다.
PC의 DNS·프록시 경로와 브라우저에 표시된 인증서도 함께 확인합니다.

CP1에서 Keycloak 로그인용 접속 주소를 확인합니다.

```bash
make headlamp-ui KUBE_CONTEXT="$KUBE_CONTEXT"
```

브라우저에서 **https://etch.samsungds.net/headlamp/** 를 열고 **Sign in**으로 Keycloak에 로그인합니다.
[Keycloak 전환 절차](OIDC.md)의 client·그룹·API server OIDC·Secret 설정을 배포 전에 완료해야 합니다.
노드 목록과 Pod 로그가 보이는지 확인합니다. port-forward는 필요하지 않습니다.

### 선택: Ubuntu 서버의 Root CA 신뢰 등록

해당 서버에서 `--cacert` 없이 HTTPS 요청할 때 신뢰 오류가 나는 경우에만 실행합니다.
이미 같은 Root CA가 등록돼 있으면 생략합니다.

```bash
sudo install -m 0644 \
  /appdata/certs/SECDS-T2RootCA.crt \
  /usr/local/share/ca-certificates/SECDS-T2RootCA.crt
sudo update-ca-certificates
```

다른 Worker에도 신뢰 설정이 필요하다면 Root CA 공개 파일만 전달합니다.
OS 신뢰 설정은 Pod나 Java의 별도 신뢰 저장소에 자동 반영되지 않을 수 있습니다.

## 공식 참고

- [OpenSSL P7B 추출](https://docs.openssl.org/3.0/man1/openssl-pkcs7/)
- [OpenSSL PFX 추출](https://docs.openssl.org/3.0/man1/openssl-pkcs12/)
- [OpenSSL 인증서 검증](https://docs.openssl.org/3.0/man1/openssl-verify/)
- [Kubernetes Ingress TLS](https://kubernetes.io/docs/concepts/services-networking/ingress/#tls)
