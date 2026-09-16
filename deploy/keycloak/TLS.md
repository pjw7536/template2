# Keycloak HTTPS 인증서와 Secret 운영 가이드

[Keycloak 배포 안내](README.md)

## 1. 역할과 적용 범위

보유한 인증서로 Traefik의 TLS 인증서 체인을 구성하고 접속 PC·서버에서 Keycloak을
신뢰하도록 설정하는 절차입니다. 사용자 제공 운영 환경을 기준으로 작성했으며,
이 문서의 존재가 실제 서버에서 적용·검증을 완료했다는 뜻은 아닙니다.

| 항목 | 현재 프로젝트 기준 |
| --- | --- |
| 도메인 | `etch-sso.samsungds.net` |
| Namespace | `etch-sso` |
| TLS Secret | `keycloak-tls` |
| TLS 종료 지점 | Traefik Pod |
| Worker IP / HTTPS 포트 | `10.172.40.87:443` — 실제 접속 경로인지 확인 |
| 명령 실행 위치 | 인증서 파일과 대상 클러스터의 kubectl 권한이 있는 CP1 |

```text
브라우저 ── HTTPS :443 ──> Traefik Pod ── HTTP :8080 ──> Keycloak Pod
                              ↑
                      keycloak-tls Secret
```

Secret은 별도로 실행하는 Pod나 서버가 아니라 Kubernetes에 저장하는 설정 데이터입니다.
`keycloak-tls`에는 `tls.crt`와 `tls.key`가 저장됩니다. Ingress가 이 Secret을 참조하고,
Traefik이 이를 읽어 HTTPS 연결에 사용합니다. Keycloak Pod가 직접 TLS 개인키를 읽지는 않습니다.

| Secret | 사용하는 Pod / 용도 |
| --- | --- |
| `keycloak-tls` | Traefik: HTTPS 인증서·개인키 |
| `keycloak-runtime` | PostgreSQL: DB 비밀번호; Keycloak: DB 비밀번호·초기 관리자·공개 URL; 설정 Job: 관리자 로그인 |
| `keycloak-oidc-settings` | 선택적인 OIDC 설정 Job: 사내 OIDC 연결값 등록 |

`internal-keycloak-stack.yaml`에는 HTTPS 포트, 도메인, TLS annotation과 Secret 참조가
포함됩니다. 실제 인증서와 개인키는 포함하지 않으므로 아래 절차로 Secret을 별도 등록합니다.
Secret 생성 명령은 최초 실행 시 생성하고, 기존 Secret이 있으면 내용을 갱신합니다.
같은 클러스터에서 Pod를 재생성해도 Secret은 유지되며, 일반적인 스택 재적용으로 덮어쓰지 않습니다.
Secret 또는 Namespace를 삭제했거나 새 클러스터를 구성했다면 다시 준비해야 합니다.

정상 HTTPS에는 두 조건이 모두 필요합니다.

- Traefik이 서버 인증서와 Intermediate CA를 제공한다.
- 접속하는 PC·서버가 Root CA를 신뢰한다.

CP1이나 Worker에 Root CA를 설치해도 Windows PC의 신뢰 설정은 바뀌지 않습니다.
각 접속 주체의 신뢰 저장소를 별도로 확인합니다.

## 2. 원본 인증서 파일

| 경로 | 용도 |
| --- | --- |
| `/appdata/certs/etch-sso.samsungds.net.pfx` | 서버 인증서·개인키 추출 |
| `/appdata/certs/etch-sso.samsungds.net.p7b` | CA 인증서 묶음 확인용 |
| `/appdata/certs/SECDS-T2IssuingCA.crt` | Intermediate CA, PEM 형식 |
| `/appdata/certs/SECDS-T2RootCA.crt` | Root CA, PEM 형식 |

개별 CA 파일이 준비된 기준이므로 P7B 추출은 필요하지 않습니다. `.crt`·`.cer` 확장자보다
실제 인코딩이 중요합니다. PFX와 개인키는 저장소나 문서에 첨부하지 않습니다.

## 3. 서버 인증서와 개인키 추출

CP1의 Bash에서 단계별로 실행합니다. 오류가 나면 다음 단계로 진행하지 않습니다.

```bash
cd /appdata/certs
umask 077
set -o pipefail
```

PFX 비밀번호는 요청되는 프롬프트에 입력합니다.

```bash
openssl pkcs12 -in etch-sso.samsungds.net.pfx -clcerts -nokeys |
openssl x509 -out keycloak-leaf.crt
```

같은 PFX에서 개인키를 추출합니다.

```bash
openssl pkcs12 -in etch-sso.samsungds.net.pfx -nocerts -nodes |
openssl pkey -out keycloak.key

chmod 600 keycloak.key
```

`keycloak.key`는 암호화되지 않은 개인키이므로 접근 권한을 제한합니다.
OpenSSL 3에서 구형 PFX 암호화 알고리즘 오류가 발생하면 해당 `openssl pkcs12` 명령에
`-legacy`를 추가합니다. 비밀번호 오류에는 해결책이 아닙니다.

## 4. 적용 전 검증과 Fullchain 생성

서버 이름과 유효기간을 확인합니다.

```bash
openssl x509 -in /appdata/certs/keycloak-leaf.crt \
  -noout -subject -issuer -dates -ext subjectAltName
```

SAN이 도메인과 일치하고 현재 시간이 유효기간 안에 있어야 합니다.
Issuer가 준비한 Intermediate CA와 연결되는지도 확인합니다.
다음 두 공개키 SHA256 값은 같아야 합니다.

```bash
openssl x509 -in /appdata/certs/keycloak-leaf.crt -pubkey -noout |
openssl pkey -pubin -outform DER |
openssl sha256

openssl pkey -in /appdata/certs/keycloak.key -pubout -outform DER |
openssl sha256
```

체인과 호스트명을 검증합니다. 결과는 `keycloak-leaf.crt: OK`여야 합니다.

```bash
openssl verify \
  -purpose sslserver \
  -verify_hostname etch-sso.samsungds.net \
  -CAfile /appdata/certs/SECDS-T2RootCA.crt \
  -untrusted /appdata/certs/SECDS-T2IssuingCA.crt \
  /appdata/certs/keycloak-leaf.crt
```

서버 인증서, Intermediate CA 순서로 결합합니다. Root CA는 일반적으로 제공 체인에 넣지 않습니다.

```bash
cat /appdata/certs/keycloak-leaf.crt \
  /appdata/certs/SECDS-T2IssuingCA.crt \
  > /appdata/certs/keycloak-fullchain.crt

grep -c 'BEGIN CERTIFICATE' /appdata/certs/keycloak-fullchain.crt
```

Intermediate CA가 하나인 이 구성에서는 인증서 개수가 `2`입니다.
개수만으로 올바른 체인을 보장하지 않으므로 앞의 검증도 통과해야 합니다.

## 5. Kubernetes TLS Secret 생성·갱신

인증서 경로는 kubectl을 실행하는 CP1의 로컬 경로입니다.
Secret 등록을 위해 개인키와 Fullchain 파일을 Worker에 복사할 필요는 없습니다.

```bash
kubectl create namespace etch-sso --dry-run=client -o yaml |
kubectl apply -f -

kubectl create secret tls keycloak-tls \
  --namespace etch-sso \
  --cert=/appdata/certs/keycloak-fullchain.crt \
  --key=/appdata/certs/keycloak.key \
  --dry-run=client -o yaml |
kubectl apply -f -

kubectl get secret keycloak-tls -n etch-sso
```

정상 출력은 `TYPE=kubernetes.io/tls`, `DATA=2`입니다.
여기서 `DATA=2`는 `tls.crt`·`tls.key` 항목 수이며 인증서 개수가 아닙니다.

개인키를 출력하지 않고 Secret에 저장된 인증서 체인만 확인합니다.

```bash
kubectl get secret keycloak-tls -n etch-sso \
  -o jsonpath='{.data.tls\.crt}' |
base64 -d > /appdata/certs/keycloak-live-fullchain.crt

grep -c 'BEGIN CERTIFICATE' /appdata/certs/keycloak-live-fullchain.crt

openssl crl2pkcs7 -nocrl \
  -certfile /appdata/certs/keycloak-live-fullchain.crt |
openssl pkcs7 -print_certs -noout
```

서버 인증서와 Intermediate CA가 포함되어 있어야 합니다.

## 6. Ingress 연결과 Traefik 확인

```bash
kubectl get ingress keycloak -n etch-sso -o yaml
```

다음 부분을 확인합니다. 아래는 확인용 발췌이며 단독 적용 파일이 아닙니다.

```yaml
metadata:
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: websecure
    traefik.ingress.kubernetes.io/router.tls: "true"
spec:
  ingressClassName: traefik
  tls:
    - hosts:
        - etch-sso.samsungds.net
      secretName: keycloak-tls
```

`spec.rules[].host`도 같은 도메인이어야 합니다. Secret과 Ingress는 같은 Namespace에
있어야 합니다. 현재 저장소 원본은 [stack.yaml](k8s/server/stack.yaml)입니다.

먼저 다음 절의 실제 endpoint를 검증합니다. 새 인증서가 반영됐으면 재시작하지 않습니다.
반영되지 않으면 Ingress 연결과 Traefik 상태를 확인합니다.

```bash
kubectl get deployment,daemonset -A | grep -i traefik
```

현재 프로젝트의 `etch-sso` Namespace, `traefik` Deployment를 재시작해야 하는 경우에만 실행합니다.
단일 인스턴스이므로 잠시 접속이 끊길 수 있습니다. Keycloak 재시작은 TLS 갱신 작업이 아닙니다.

```bash
kubectl rollout restart deployment/traefik -n etch-sso
kubectl rollout status deployment/traefik -n etch-sso
```

## 7. 실제 HTTPS endpoint 검증

직접 Worker에 연결해 제공 체인과 호스트명을 검증합니다.

```bash
openssl s_client \
  -connect 10.172.40.87:443 \
  -servername etch-sso.samsungds.net \
  -verify_hostname etch-sso.samsungds.net \
  -verify_return_error \
  -CAfile /appdata/certs/SECDS-T2RootCA.crt \
  -showcerts </dev/null
```

`-servername`은 SNI 지정이며 호스트명 검사는 `-verify_hostname`이 수행합니다.
`-verify_return_error`는 인증서 검증 오류를 실패로 처리합니다.
체인 0번이 서버 인증서, 1번이 Intermediate CA인지 확인합니다.
검증 결과는 `Verify return code: 0 (ok)`여야 합니다.

이 결과는 해당 IP가 제공한 인증서를 명시한 Root CA와 호스트명으로 검증한 것입니다.
Windows PC의 신뢰 설정이나 브라우저 접속 경로까지 검증한 것은 아닙니다.

실제 도메인 경로도 확인합니다.

```bash
getent hosts etch-sso.samsungds.net

curl -v \
  --cacert /appdata/certs/SECDS-T2RootCA.crt \
  https://etch-sso.samsungds.net/ -o /dev/null
```

직접 IP 검증만 성공하면 DNS·LB·프록시 등 실제 경로를 확인합니다.
HTTP 404 등의 응답은 TLS 검증 성공 여부와 별도로 라우팅을 점검합니다.

## 8. Ubuntu 클라이언트의 Root CA 신뢰

해당 서버가 HTTPS 클라이언트로 요청할 때 기본 신뢰 검증이 실패하는 경우에만 진행합니다.

```bash
curl -v https://etch-sso.samsungds.net/ -o /dev/null
```

`--cacert`를 지정하면 성공하고 위 요청은 신뢰 오류로 실패한다면 해당 노드에 Root CA를 등록합니다.

```bash
sudo install -m 0644 /appdata/certs/SECDS-T2RootCA.crt \
  /usr/local/share/ca-certificates/SECDS-T2RootCA.crt

sudo update-ca-certificates

curl -v https://etch-sso.samsungds.net/ -o /dev/null
```

PEM 형식의 `.crt` 파일을 사용합니다. 신뢰가 필요한 CP1·Worker 각각에서 수행하며
Worker에는 Root CA 공개 인증서만 전달하면 됩니다. 호스트 OS 신뢰 저장소 변경이
컨테이너나 별도 Java/Python 저장소에 자동 적용되지는 않을 수 있습니다.
Pod 내부에서만 실패하면 해당 애플리케이션의 신뢰 저장소를 확인합니다.

## 9. Windows 브라우저 경고 확인

`https://etch-sso.samsungds.net` 도메인으로 접속합니다. IP SAN이 없는 인증서에서
IP 주소로 접속하면 이름 불일치 경고가 발생할 수 있습니다.

- 현재 사용자 저장소: `Win + R` → `certmgr.msc`
- 로컬 컴퓨터 저장소: `Win + R` → `certlm.msc`

| 저장소 | 확인할 인증서 |
| --- | --- |
| 신뢰할 수 있는 루트 인증 기관 → 인증서 | `SECDS-T2RootCA` |
| 중간 인증 기관 → 인증서 | 필요 시 `SECDS-T2IssuingCA` |

서버가 Intermediate CA를 제공하면 PC에 중간 인증서를 반드시 따로 설치해야 하는 것은 아닙니다.
Root CA가 없다면 회사 인증서 배포 정책에 따라 설치하고 관리 PC의 GPO 배포 여부도 확인합니다.
서버 검증만으로 브라우저 경고 원인을 단정하지 말고 오류 코드와 실제 표시 인증서를 확인합니다.

| 증상 | 확인 항목 |
| --- | --- |
| `NET::ERR_CERT_AUTHORITY_INVALID` | Root CA 신뢰, Intermediate 누락, 보안 프록시 인증서 |
| `NET::ERR_CERT_COMMON_NAME_INVALID` | URL과 SAN, IP 접속, 기본 인증서 노출 |
| `NET::ERR_CERT_DATE_INVALID` | 유효기간, PC·서버 시간 |
| Traefik 기본 인증서 표시 | Ingress 도메인·Secret 참조, 실제 endpoint |
| 직접 IP 검증 성공, 브라우저만 실패 | PC DNS·LB·프록시 경로, 실제 인증서, 신뢰 정책 |

## 10. 완료 기준

- [ ] 서버 인증서와 개인키의 공개키 SHA256이 같다.
- [ ] 로컬 체인·호스트명 검증 결과가 OK다.
- [ ] Fullchain에 서버 인증서와 Intermediate CA가 올바른 순서로 들어 있다.
- [ ] `etch-sso/keycloak-tls`에 Fullchain과 개인키가 저장되어 있다.
- [ ] Ingress의 도메인과 Secret 참조가 맞다.
- [ ] 실제 endpoint 검증 결과가 `0 (ok)`다.
- [ ] 필요한 Ubuntu 클라이언트에서 `--cacert` 없이 검증이 성공한다.
- [ ] Windows PC에서 도메인 접속 시 인증서 경고가 없다.

서버 배포 및 사용자 매핑 절차는 [Keycloak 배포 안내](README.md)를 따릅니다.
