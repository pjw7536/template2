# Keycloak 설치 준비

[Keycloak 가이드](../README.md)

설치·업데이트 절차는 [Keycloak 가이드](../README.md)에 있습니다. 이 문서는 설치 범위, Worker 확인, env 키의 의미, 인증서·CA 준비 방법입니다.

- [설치 범위](#설치-범위)
- [Worker 디스크 확인](#worker-디스크-확인)
- [환경설정](#환경설정)
- [TLS·CA 준비](#tlsca-준비)

## 설치 범위

| 항목 | 현재 원본 기준 |
| --- | --- |
| 실행 방식 | Kubernetes, namespace `etch-sso` |
| Keycloak / PostgreSQL | 26.7.1 / 16, 각각 단일 replica |
| 데이터 저장 | worker의 `/appdata/keycloak-postgres`, 50Gi 정적 local PV |
| 기본 worker | `khplane01w09` |
| HTTPS | 공용 Traefik(앱 `ingress`)이 worker host port 80/443에서 종료 |
| 최초 realm | `etch`. 사내 IdP·앱 client는 별도 설정 |

관리 호스트에 Python 3.10+·Bash·kubectl·OpenSSL·Make가 필요합니다. Airflow·Helm·Docker는 필요하지 않습니다.

이 구성은 단일 worker의 로컬 디스크에 의존하므로 HA가 아닙니다. PostgreSQL 외부 백업을 별도로 준비합니다.

## Worker 디스크 확인

`keycloak-up`이 PV를 처음 만들 때 PostgreSQL 이미지 Job으로 DB 폴더를 root 소유 0700으로 만듭니다. 기존 폴더와 DB 파일은 바꾸지 않습니다.
`/appdata`가 데이터 디스크에 마운트돼 있지 않으면 폴더가 OS 디스크에 만들어지므로 배포 전에 마운트를 확인합니다. 데이터 경로의 기준은 [Worker 앱 데이터 경로](../../shared/docs/infrastructure/operations.md#worker-앱-데이터-경로와-이전)에 있습니다.

실행 위치는 원본(`k8s/server/stack.yaml`의 `nodeSelector`)에 지정한 worker `khplane01w09`입니다. [노드 SSH](../../shared/docs/infrastructure/access.md#노드-ssh)의 방법으로 실행합니다.

[조회] 마운트와 여유 공간, 기존 폴더를 확인합니다.

```bash
findmnt -T /appdata
df -hT /appdata
sudo -n ls -ld /appdata/keycloak-postgres || true
```

성공: `/appdata`가 계획한 데이터 디스크의 파일시스템에 있고 여유 공간이 PV 용량 50Gi보다 큽니다. 폴더가 없다는 출력은 정상이며 `keycloak-up`이 만듭니다. 폴더가 이미 있고 PV `keycloak-postgres-data`가 없으면 이전 설치의 DB일 수 있으므로 지우지 않고 [기존 DB 복구](03-operations.md#기존-dbnamespace를-복구하는-경우)를 먼저 봅니다.

[변경] 폴더를 직접 준비해야 할 때만 같은 worker에서 실행합니다. 보통은 `keycloak-up`이 만들므로 필요하지 않습니다.

```bash
sudo -n install -d -m 0700 /appdata/keycloak-postgres
sudo -n ls -ld /appdata/keycloak-postgres
```

성공: `drwx------`와 소유자 `root root`가 출력됩니다.

worker의 80/443 포트는 공용 Traefik이 쓰며 확인 방법은 [ingress 가이드의 사전 준비](../../shared/ingress/README.md#사전-준비)에 있습니다.

## 환경설정

설정 파일은 `KEY=값` 형식으로 작성합니다. 값을 따옴표로 감싸거나 파일을 셸 코드로 `source`하지 않습니다.
파일만 편집하면 서버가 바뀌지 않으며, 가이드의 배포 명령이 Secret과 설정 Job을 준비합니다.

기본 입력은 `deploy/keycloak/env/prod.env`입니다. 저장소의 값과 다른 값을 써야 하면 저장소 파일을 고치지 않고 [운영 입력 파일](../../shared/docs/infrastructure/access.md#운영-입력-파일)의 방법으로 복사본을 만들어, 검사·배포·설정·대조의 모든 명령에 **같은 파일 경로**를 `KEYCLOAK_ENV="<env 절대 경로>"`로 전달합니다. 설정을 두 곳에 중복 관리하지 않습니다.

[검사] 클러스터에 접속하지 않는 정적 검사입니다. 저장소의 기본 env만 검사하며 실제 credential·클러스터 연결·worker 디스크 상태는 검증하지 않습니다.

```bash
make env-check APP=keycloak PROFILE=prod COMPONENT=server
make server-check APP=keycloak PROFILE=prod
```

성공: `설정 검사 통과`와 `서버 원본 검사 통과: keycloak`. 실제 입력과 클러스터 검사는 `make keycloak-check KUBE_CONTEXT="<context>"`가 합니다.

### 서버 기동용 값

| 항목 | 의미 |
| --- | --- |
| `postgres-password` | 새 Keycloak PostgreSQL의 비밀번호 |
| `bootstrap-admin-username` | 최초 관리자 계정 |
| `bootstrap-admin-password` | 최초 관리자 비밀번호. 설정 Job도 같은 계정 사용 |
| `keycloak-public-url` | 공개 HTTPS URL. 경로와 끝의 `/` 없음 |

비밀번호는 각각 `openssl rand -hex 32`로 생성합니다.
`keycloak-up`이 이 값으로 `etch-sso/keycloak-runtime` Secret을 없을 때만 만들며 Realm·프로필·IdP mapper Job은 이 Secret으로 인증합니다. Secret이 이미 있고 env와 다르면 배포가 중단됩니다([Secret 불일치와 기존 DB 복구](03-operations.md#secret-불일치와-기존-db-복구)).
서버 기동에는 사내·Portal client secret이 필요하지 않습니다.

### 사내 Identity Provider용 값

같은 env 파일에 입력합니다. 사내 AD FS에서 발급받은 client를 사용하며, 발급과 redirect URI 등록은 [AD FS](../../shared/docs/infrastructure/access.md#ad-fs) 절의 방법으로 합니다.

| 항목 | 입력 |
| --- | --- |
| `CORP_OIDC_DISCOVERY_URL` | 사내 metadata URL. 저장소 파일에 설정돼 있으므로 대상 주소 확인 |
| `CORP_OIDC_CLIENT_ID` | 사내 client ID |
| `CORP_OIDC_CLIENT_SECRET` | 사내 client secret |
| `CORP_OIDC_CLIENT_AUTH_METHOD` | `client_secret_post` |
| `CORP_OIDC_VALIDATE_SIGNATURE` | `true` |

Authorization·Token·JWKS·UserInfo·Logout URL과 issuer는 [Discovery](02-configure.md#discovery-해석-규칙)로 해석하므로 입력하지 않습니다.
사내 client의 redirect URI는 `<공개 Keycloak URL>/realms/etch/broker/oidc/endpoint`이며 AD FS에 등록돼 있어야 합니다.

[검사] 입력과 Discovery 조회를 확인합니다. 클러스터를 바꾸지 않습니다. 다른 env 파일을 쓰면 `KEYCLOAK_ENV="<env 절대 경로>"`를 붙입니다.

```bash
make keycloak-oidc-check KUBE_CONTEXT="<context>"
```

성공: `사전 검사 통과`. `설정 중단: 필수 설정 누락: …`이나 `설정 중단: 실제 값으로 교체할 설정: …`이면 표시된 키에 발급값이 없는 것입니다.

SDWT 등록의 관리자 인증과 Portal·Headlamp 입력은 Keycloak 서버 입력이 아니며 [로그인·그룹·앱 연결](02-configure.md)에서 다룹니다.

## TLS·CA 준비

인증서 파일은 [인증서 발급](../../shared/docs/infrastructure/access.md#인증서-발급) 절의 방법으로 준비해 아래 폴더에 둡니다. 공용 TLS 등록은 `make ops-deploy APP=keycloak`의 준비 검사가 자동으로 수행하고, 인증서를 갱신할 때 직접 쓰는 명령은 [공용 TLS 등록](../../README.md#공용-tls-등록)에 있습니다.

| 항목 | 운영값 |
| --- | --- |
| namespace | `etch-sso` |
| Ingress 이름 | `keycloak` |
| 도메인 | `sso.etch.samsungds.net` |
| 인증서 폴더 | `deploy/shared/certs/sso.etch.samsungds.net/` |
| 인증서·개인키 | `fullchain.crt`, `private.key` |
| TLS Secret | `etch-sso/traefik-tls` |
| TLS 종료 | Traefik |

공개 URL은 경로와 끝의 `/`가 없는 HTTPS URL이며 Ingress 도메인·인증서 SAN과 맞아야 합니다. DNS·APP VIP는 [네트워크 정보](../../shared/docs/infrastructure/network.md)를 따릅니다.
PFX·P7B 추출, fullchain 구성·검증은 [공용 인증서 준비](../../shared/docs/certificates/prepare.md), 등록 대상 선택과 등록·갱신은 [공용 인증서 적용](../../shared/docs/certificates/apply.md#1-적용할-사이트와-대상-클러스터-선택)을 따릅니다.
Keycloak의 개인키는 TLS를 종료하는 Traefik이 사용하며 API server용 CA 파일과는 다릅니다. Keycloak 배포는 `etch-sso/traefik-tls`에 등록된 인증서를 검사하며 인증서 파일을 다시 읽지 않습니다. 인증서를 배치해도 realm·IdP·mapper 설정은 만들어지지 않습니다.

서버는 중간 인증서를 포함한 fullchain을 제공하고, 접속하는 PC·서버가 루트 CA를 신뢰해야 합니다.
관리 호스트의 신뢰 설정은 PC·Headlamp Pod·Kubernetes API server에 자동으로 전달되지 않습니다.

| 대상 | 안내 |
| --- | --- |
| Ubuntu 서버·Windows PC | [클라이언트 PC 신뢰 등록](../../shared/docs/certificates/apply.md#클라이언트-pc-신뢰-등록) |
| 관리 API 도구·smoke | [사내 CA 묶음](../../README.md#사내-ca-묶음) |
| Headlamp Pod | [Headlamp TLS](../../headlamp/docs/01-prepare.md#tlsca-준비) |
| Kubernetes API server | [API server OIDC](../../shared/docs/kubernetes/oidc.md) |

호스트 OS의 신뢰 설정이 컨테이너나 별도 Java/Python 신뢰 저장소에 자동 적용되지는 않습니다. Pod 내부에서만 실패하면 해당 애플리케이션의 신뢰 저장소를 확인합니다.
