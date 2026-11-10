# Keycloak 설치 준비

[앱 안내](../README.md)

- [서버 준비](#서버-준비)
- [환경설정](#환경설정)
- [TLS·CA 준비](#tlsca-준비)

## 서버 준비

입력 설명: [환경설정](#환경설정) · [TLS 준비](#tlsca-준비)

이 문서는 PostgreSQL·Keycloak·Traefik 서버 스택을 준비할 때 사용합니다.
이 문서에서 도구·Worker·env·인증서를 준비한 뒤 [서버 배포](02-deploy.md)로 진행합니다.

### 설치 범위와 준비물

| 항목 | 현재 원본 기준 |
| --- | --- |
| 실행 방식 | Kubernetes, namespace `etch-sso` |
| Keycloak / PostgreSQL | 26.7.1 / 16, 각각 단일 replica |
| 데이터 저장 | worker의 `/appdata/keycloak-postgres`, 50Gi 정적 local PV |
| 기본 worker | `khplane01w09` |
| HTTPS | Traefik이 worker host port 80/443에서 종료 |
| 최초 realm | `etch`. 사내 IdP·앱 client는 별도 설정 |

실행 호스트에 Python 3.10+·Bash·kubectl·OpenSSL이 필요합니다. Keycloak 단독 배포에 Airflow·Helm·Docker는 필요하지 않습니다.
서버 선택 checkout에는 루트 Makefile과 필요한 `deploy` 파일이 있어야 합니다. [서버 checkout](../../shared/docs/operations/01-checkout.md#선택-checkout)을 참고하세요.

이 구성은 단일 worker의 로컬 디스크에 의존하므로 HA가 아닙니다. PostgreSQL 외부 백업을 별도로 준비합니다.

### 실행 호스트 준비

클러스터 관리 호스트의 Bash에서 실제 저장소 경로를 입력합니다.

```bash
read -r -p '저장소 절대 경로: ' KEYCLOAK_REPO_DIR
cd "$KEYCLOAK_REPO_DIR"
ls Makefile deploy/keycloak/scripts/up.py
python3 --version
bash --version
kubectl version --client
openssl version
make --version
kubectl config current-context
kubectl config get-contexts
read -r -p '배포할 Kubernetes context: ' KEYCLOAK_KUBE_CONTEXT
```

경로·도구 확인이 성공한 뒤 진행합니다. context는 목록의 `NAME` 값이며 빈 값으로 두지 않습니다.
아래 명령은 같은 터미널에서 실행합니다. Worker 작업만 해당 노드에 접속해 수행합니다.

### 1. Worker 디스크·포트 준비

원본에 지정한 worker에서 관리자 권한으로 수행합니다.

```bash
sudo install -d -m 0700 /appdata/keycloak-postgres
df -h /appdata/keycloak-postgres
sudo ss -lntp | grep -E ':(80|443)[[:space:]]' || true
```

디스크 공간과 80/443 포트 충돌을 확인합니다. 원격 worker 작업 권한이 없다면 node 관리 담당자가 수행해야 합니다.

### 2. env·DNS·인증서 준비

```text
deploy/keycloak/env/prod.env                   # 서버 설정·credential
deploy/shared/certs/sso.etch.samsungds.net/     # fullchain.crt, private.key
```

[env 안내](#환경설정)의 서버 기동용 네 항목을 입력합니다.
서버 기동에는 사내·Portal client secret이 필요하지 않습니다.

공개 URL은 경로와 끝의 `/`가 없는 HTTPS URL이어야 하며 Ingress 도메인·인증서 SAN과 맞아야 합니다.
DNS·APP VIP는 [네트워크 정보](../../shared/docs/infrastructure/network.md), 인증서 준비는 [TLS 안내](#tlsca-준비)를 따릅니다.

인증서 파일을 배치한 뒤 [공용 TLS 등록](../../shared/docs/certificates/apply.md#2-2-kubernetes-tls-secret에-등록-또는-갱신)을 수행합니다.

```bash
make ingress-tls-up KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" TLS_HOST=sso.etch.samsungds.net \
  TLS_CERT_FILE="$PWD/deploy/shared/certs/sso.etch.samsungds.net/fullchain.crt" \
  TLS_KEY_FILE="$PWD/deploy/shared/certs/sso.etch.samsungds.net/private.key"
```

Keycloak 배포는 등록된 인증서를 검사하며 기본적으로 인증서 파일을 다시 읽거나 갱신하지 않습니다.

```bash
vi deploy/keycloak/env/prod.env
chmod 600 deploy/keycloak/env/prod.env
make env-check APP=keycloak PROFILE=prod COMPONENT=server
```

서버 원본만 검사하려면 `make server-check APP=keycloak PROFILE=prod`를 사용합니다.
이 정적 검사는 실제 credential·클러스터 연결·worker 디스크 상태를 검증하지 않습니다.

**완료 기준:** 위 준비 항목과 실행 입력을 확인했습니다. 같은 Bash 터미널에서 [검사·배포](02-deploy.md)로 진행합니다.

## 환경설정

이 문서는 입력 위치와 의미만 설명합니다. 파일 편집·검사·적용 명령은 실행 문서를 따릅니다.

설정 파일은 `KEY=값` 형식으로 작성합니다. 값을 따옴표로 감싸거나 파일을 셸 코드로 `source`하지 않습니다.

### 서버 기동용 값

`deploy/keycloak/env/prod.env`에 입력합니다.

| 항목 | 의미 |
| --- | --- |
| `postgres-password` | 새 Keycloak PostgreSQL의 비밀번호 |
| `bootstrap-admin-username` | 최초 관리자 계정 |
| `bootstrap-admin-password` | 최초 관리자 비밀번호. 설정 Job도 같은 계정 사용 |
| `keycloak-public-url` | 공개 HTTPS URL. 경로와 끝의 `/` 없음 |

서버 설치 도구가 `etch-sso/keycloak-runtime` Secret을 준비합니다.
Realm·프로필·IdP mapper Job은 이 Secret으로 인증하므로 별도 관리자 값을 입력하지 않습니다.

### 사내 Identity Provider용 값

같은 `deploy/keycloak/env/prod.env`에 입력합니다. 사내 AD FS에서 발급받은 client를 사용합니다.

| 항목 | 입력 |
| --- | --- |
| `CORP_OIDC_DISCOVERY_URL` | 사내 metadata URL. 저장소 파일에 설정돼 있으므로 대상 주소 확인 |
| `CORP_OIDC_CLIENT_ID` | 사내 client ID |
| `CORP_OIDC_CLIENT_SECRET` | 사내 client secret |
| `CORP_OIDC_CLIENT_AUTH_METHOD` | `client_secret_post` |
| `CORP_OIDC_VALIDATE_SIGNATURE` | `true` |

Authorization·Token·JWKS·UserInfo·Logout URL과 issuer는 별도로 입력하지 않습니다.
[Discovery](05-reference.md#oidc-discovery)가 제공하는 값을 해석합니다.

사내 client의 redirect URI는 `<공개 Keycloak URL>/realms/etch/broker/oidc/endpoint`입니다.

### SDWT 관리자 인증

SDWT 등록은 [연결과 인증](03-configure.md#2-연결과-인증)의 환경변수와 CSV를 사용합니다.
관리자 API 도구는 Kubernetes Secret을 자동으로 읽지 않습니다.

### 앱 입력은 Keycloak 준비 후 작성

Portal은 `deploy/portal/env/prod/api.env`, Headlamp는 `deploy/headlamp/env/k8s.env`와 전용 Secret을 사용합니다.
이 값은 Keycloak 서버 설치 입력이 아닙니다. [앱 연결](03-configure.md#앱-연결)에서 각 앱의 안내를 따릅니다.

사내 IdP와 업무 앱의 client ID·secret은 각각 준비합니다.

### 파일과 적용의 차이

설정 파일만 편집하면 서버가 바뀌지 않습니다. 실행 문서의 검사·적용 명령이 Secret과 설정 Job을 준비합니다.
인증서·개인키는 [TLS 준비](#tlsca-준비)의 파일 경로를 사용합니다.

## TLS·CA 준비

이 문서는 Keycloak 사이트의 HTTPS 인증서 준비와, 접속하는 PC·서버의 CA 신뢰 설정을 설명합니다.
인증서를 배치해도 realm·IdP·mapper 설정이 만들어지는 것은 아닙니다.

### 현재 파일과 Secret

| 항목 | 운영값 |
| --- | --- |
| namespace | `etch-sso` |
| Ingress 이름 | `keycloak` |
| 도메인 | `sso.etch.samsungds.net` |
| 인증서 폴더 | `deploy/shared/certs/sso.etch.samsungds.net/` |
| 인증서·개인키 | `fullchain.crt`, `private.key` |
| TLS Secret | `etch-sso/traefik-tls` |
| TLS 종료 | Traefik |

### 인증서 준비와 적용

[공용 인증서 안내](../../shared/docs/certificates/prepare.md)의 **Keycloak 사이트 선택**을 사용합니다.
PFX·P7B 추출, fullchain 구성과 검증을 한곳에서 관리합니다.

Keycloak의 개인키는 TLS를 종료하는 Traefik이 사용하며 API server용 CA 파일과는 다릅니다.

준비한 파일을 공용 등록 명령으로 먼저 등록한 뒤 [서버 준비·배포](../README.md)를 진행합니다.
Keycloak 배포는 공용 인증서를 검사하며 PEM 파일을 다시 준비할 필요가 없습니다.
이 문서에서는 서버 배포 명령을 중복 실행하지 않습니다.

### 신뢰 설정의 구분

서버가 중간 인증서를 포함한 fullchain을 제공하고, 접속하는 PC·서버가 루트 CA를 신뢰해야 합니다.
CP1의 신뢰 설정은 PC·Headlamp Pod·Kubernetes API server에 자동으로 전달되지 않습니다.
Headlamp와 API server의 신뢰 설정은 [Headlamp TLS](../../headlamp/docs/01-prepare.md#tlsca-준비)와 [API server 설정](../../headlamp/docs/02-authentication.md#api-server-인증)를 따릅니다.

### 클라이언트 신뢰: Ubuntu 클라이언트의 Root CA 신뢰

해당 서버가 HTTPS 클라이언트로 요청할 때 기본 신뢰 검증이 실패하는 경우에만 진행합니다.

```bash
curl -v https://sso.etch.samsungds.net/ -o /dev/null
```

`--cacert`를 지정하면 성공하고 위 요청은 신뢰 오류로 실패한다면 해당 노드에 Root CA를 등록합니다.

```bash
sudo install -m 0644 deploy/shared/certs/ca/SECDS-T2RootCA.crt \
  /usr/local/share/ca-certificates/SECDS-T2RootCA.crt

sudo update-ca-certificates

curl -v https://sso.etch.samsungds.net/ -o /dev/null
```

PEM 형식의 `.crt` 파일을 사용합니다. 신뢰가 필요한 CP1·Worker 각각에서 수행합니다.
Worker에는 Root CA 공개 인증서만 전달하면 됩니다.

호스트 OS의 신뢰 설정이 컨테이너나 별도 Java/Python 신뢰 저장소에 자동 적용되지는 않을 수 있습니다.
Pod 내부에서만 실패하면 해당 애플리케이션의 신뢰 저장소를 확인합니다.

### 클라이언트 신뢰: Windows 브라우저 경고 확인

`https://sso.etch.samsungds.net` 도메인으로 접속합니다. IP SAN이 없는 인증서에서
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
| Traefik 기본 인증서 표시 | Ingress 도메인·공용 인증서 등록과 마운트, 실제 endpoint |
| 직접 IP 검증 성공, 브라우저만 실패 | PC DNS·LB·프록시 경로, 실제 인증서, 신뢰 정책 |
