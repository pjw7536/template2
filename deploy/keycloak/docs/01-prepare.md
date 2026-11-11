# Keycloak 설치 준비

[앱 안내](../README.md)

- [서버 준비](#서버-준비)
- [환경설정](#환경설정)
- [TLS·CA 준비](#tlsca-준비)

## 서버 준비

**목적:** PostgreSQL·Keycloak·Traefik 서버 스택 배포 전에 실행 호스트·Worker·env·인증서를 준비합니다.

### 설치 범위와 준비물

| 항목 | 현재 원본 기준 |
| --- | --- |
| 실행 방식 | Kubernetes, namespace `etch-sso` |
| Keycloak / PostgreSQL | 26.7.1 / 16, 각각 단일 replica |
| 데이터 저장 | worker의 `/appdata/keycloak-postgres`, 50Gi 정적 local PV |
| 기본 worker | `khplane01w09` |
| HTTPS | Traefik이 worker host port 80/443에서 종료 |
| 최초 realm | `etch`. 사내 IdP·앱 client는 별도 설정 |

실행 호스트에 Python 3.10+·Bash·kubectl·OpenSSL·Make가 필요합니다. Airflow·Helm·Docker는 필요하지 않습니다.

이 구성은 단일 worker의 로컬 디스크에 의존하므로 HA가 아닙니다. PostgreSQL 외부 백업을 별도로 준비합니다.

### 실행 위치와 입력

클러스터 관리 호스트의 Bash에서 실제 저장소 경로와 배포 context를 입력합니다.

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

context는 목록의 `NAME` 값이며 빈 값으로 두지 않습니다. 이후 명령은 같은 터미널에서 실행하고 Worker 작업만 해당 노드에서 수행합니다.

### 1. Worker 디스크·포트 준비

원본에 지정한 worker에서 관리자 권한으로 수행합니다. 원격 worker 작업 권한이 없다면 node 관리 담당자가 수행합니다.

```bash
sudo install -d -m 0700 /appdata/keycloak-postgres
df -h /appdata/keycloak-postgres
sudo ss -lntp | grep -E ':(80|443)[[:space:]]' || true
```

**기대 결과:** 디렉터리가 있고 디스크 여유가 충분하며 80/443을 사용하는 다른 프로세스가 없습니다.

### 2. env 작성과 검사

[환경설정](#환경설정)의 서버 기동용 네 항목을 `deploy/keycloak/env/prod.env`에 입력합니다. 서버 기동에는 사내·Portal client secret이 필요하지 않습니다.

```bash
vi deploy/keycloak/env/prod.env
chmod 600 deploy/keycloak/env/prod.env
make env-check APP=keycloak PROFILE=prod COMPONENT=server
make server-check APP=keycloak PROFILE=prod
```

**기대 결과:** 두 검사가 통과합니다. 이 정적 검사는 실제 credential·클러스터 연결·worker 디스크 상태를 검증하지 않습니다.

### 3. TLS 인증서 등록

공개 URL은 경로와 끝의 `/`가 없는 HTTPS URL이며 Ingress 도메인·인증서 SAN과 맞아야 합니다.
DNS·APP VIP는 [네트워크 정보](../../shared/docs/infrastructure/network.md)를 따릅니다.

`deploy/shared/certs/sso.etch.samsungds.net/`에 `fullchain.crt`, `private.key`를 배치한 뒤 [공용 TLS 등록](../../shared/docs/certificates/apply.md#2-공용-tls-secret-등록갱신--cp1)을 수행합니다.

```bash
make ingress-tls-up KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" TLS_HOST=sso.etch.samsungds.net \
  TLS_CERT_FILE="$PWD/deploy/shared/certs/sso.etch.samsungds.net/fullchain.crt" \
  TLS_KEY_FILE="$PWD/deploy/shared/certs/sso.etch.samsungds.net/private.key"
```

**기대 결과:** `etch-sso/traefik-tls`에 Keycloak 도메인 인증서가 등록됩니다. Keycloak 배포는 등록된 인증서를 검사하며 인증서 파일을 다시 읽지 않습니다.

**다음 단계:** 같은 터미널에서 [검사·배포](02-deploy.md)로 진행합니다.

## 환경설정

설정 파일은 `KEY=값` 형식으로 작성합니다. 값을 따옴표로 감싸거나 파일을 셸 코드로 `source`하지 않습니다.
파일만 편집하면 서버가 바뀌지 않으며, 실행 문서의 검사·적용 명령이 Secret과 설정 Job을 준비합니다.

### 서버 기동용 값

`deploy/keycloak/env/prod.env`에 입력합니다.

| 항목 | 의미 |
| --- | --- |
| `postgres-password` | 새 Keycloak PostgreSQL의 비밀번호 |
| `bootstrap-admin-username` | 최초 관리자 계정 |
| `bootstrap-admin-password` | 최초 관리자 비밀번호. 설정 Job도 같은 계정 사용 |
| `keycloak-public-url` | 공개 HTTPS URL. 경로와 끝의 `/` 없음 |

서버 배포 도구가 `etch-sso/keycloak-runtime` Secret을 준비하며 Realm·프로필·IdP mapper Job은 이 Secret으로 인증합니다.

### 사내 Identity Provider용 값

같은 `deploy/keycloak/env/prod.env`에 입력합니다. 사내 AD FS에서 발급받은 client를 사용합니다.

| 항목 | 입력 |
| --- | --- |
| `CORP_OIDC_DISCOVERY_URL` | 사내 metadata URL. 저장소 파일에 설정돼 있으므로 대상 주소 확인 |
| `CORP_OIDC_CLIENT_ID` | 사내 client ID |
| `CORP_OIDC_CLIENT_SECRET` | 사내 client secret |
| `CORP_OIDC_CLIENT_AUTH_METHOD` | `client_secret_post` |
| `CORP_OIDC_VALIDATE_SIGNATURE` | `true` |

Authorization·Token·JWKS·UserInfo·Logout URL과 issuer는 [Discovery](03-configure.md#discovery-해석-규칙)로 해석하므로 입력하지 않습니다.
사내 client의 redirect URI는 `<공개 Keycloak URL>/realms/etch/broker/oidc/endpoint`입니다.

SDWT 등록의 관리자 인증과 Portal·Headlamp 입력은 Keycloak 서버 입력이 아니며 [Keycloak 설정](03-configure.md)에서 다룹니다.

## TLS·CA 준비

| 항목 | 운영값 |
| --- | --- |
| namespace | `etch-sso` |
| Ingress 이름 | `keycloak` |
| 도메인 | `sso.etch.samsungds.net` |
| 인증서 폴더 | `deploy/shared/certs/sso.etch.samsungds.net/` |
| 인증서·개인키 | `fullchain.crt`, `private.key` |
| TLS Secret | `etch-sso/traefik-tls` |
| TLS 종료 | Traefik |

PFX·P7B 추출, fullchain 구성·검증은 [공용 인증서 준비](../../shared/docs/certificates/prepare.md), 등록 대상 선택은 [공용 인증서 적용](../../shared/docs/certificates/apply.md#1-적용할-사이트와-대상-클러스터-선택)을 따릅니다.
Keycloak의 개인키는 TLS를 종료하는 Traefik이 사용하며 API server용 CA 파일과는 다릅니다. 인증서를 배치해도 realm·IdP·mapper 설정은 만들어지지 않습니다.

서버는 중간 인증서를 포함한 fullchain을 제공하고, 접속하는 PC·서버가 루트 CA를 신뢰해야 합니다.
CP1의 신뢰 설정은 PC·Headlamp Pod·Kubernetes API server에 자동으로 전달되지 않습니다.

| 대상 | 안내 |
| --- | --- |
| Ubuntu 서버·Windows PC | [클라이언트 PC 신뢰 등록](../../shared/docs/certificates/apply.md#클라이언트-pc-신뢰-등록) |
| Headlamp Pod | [Headlamp TLS](../../headlamp/docs/01-prepare.md#tlsca-준비) |
| Kubernetes API server | [API server OIDC](../../shared/docs/kubernetes/oidc.md) |

호스트 OS의 신뢰 설정이 컨테이너나 별도 Java/Python 신뢰 저장소에 자동 적용되지는 않습니다. Pod 내부에서만 실패하면 해당 애플리케이션의 신뢰 저장소를 확인합니다.
