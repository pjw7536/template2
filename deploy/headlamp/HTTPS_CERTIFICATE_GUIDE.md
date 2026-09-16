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

다음 파일을 CP1의 `/appdata/certs`에 준비합니다.

```text
etch.samsungds.net.pfx
etch.samsungds.net.p7b
SECDS-T2IssuingCA.crt
SECDS-T2RootCA.crt
```

CA 파일은 기존에 사용한 **PEM 형식**을 전제로 합니다. 이번 인증서와 맞는지는 3단계에서 확인합니다.
개별 CA 파일이 있으므로 P7B 추출은 필요하지 않습니다.
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

## 4. Fullchain 생성

서버 인증서 다음에 Intermediate CA를 넣습니다. Root CA는 넣지 않습니다.

```bash
cat etch-leaf.crt SECDS-T2IssuingCA.crt > etch-fullchain.crt

grep -c 'BEGIN CERTIFICATE' etch-fullchain.crt
```

중간 CA가 하나인 현재 구성에서는 `2`가 나와야 합니다.

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

CP1에서 로그인 토큰을 발급합니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n headlamp create token headlamp-viewer --duration=1h
```

브라우저에서 **https://etch.samsungds.net/headlamp/** 를 열고 토큰으로 로그인합니다.
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

- [OpenSSL PFX 추출](https://docs.openssl.org/3.0/man1/openssl-pkcs12/)
- [OpenSSL 인증서 검증](https://docs.openssl.org/3.0/man1/openssl-verify/)
- [Kubernetes Ingress TLS](https://kubernetes.io/docs/concepts/services-networking/ingress/#tls)
