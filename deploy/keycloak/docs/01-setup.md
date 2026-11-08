# Keycloak 서버 준비

[앱 안내](../README.md) · [전체 배포 안내](../../README.md)

입력 설명: [환경설정](02-environment.md) · [TLS 준비](03-tls.md)

이 문서는 PostgreSQL·Keycloak·Traefik 서버 스택을 준비할 때 사용합니다.
이 문서에서 도구·Worker·env·인증서를 준비한 뒤 [서버 배포](04-deploy.md)로 진행합니다.

## 설치 범위와 준비물

| 항목 | 현재 원본 기준 |
| --- | --- |
| 실행 방식 | Kubernetes, namespace `etch-sso` |
| Keycloak / PostgreSQL | 26.7.1 / 16, 각각 단일 replica |
| 데이터 저장 | worker의 `/appdata/keycloak-postgres`, 50Gi 정적 local PV |
| 기본 worker | `khplane01w09` |
| HTTPS | Traefik이 worker host port 80/443에서 종료 |
| 최초 realm | `etch`. 사내 IdP·앱 client는 별도 설정 |

실행 호스트에 Python 3.10+·Bash·kubectl·OpenSSL이 필요합니다. Keycloak 단독 배포에 Airflow·Helm·Docker는 필요하지 않습니다.
서버 선택 checkout에는 루트 Makefile과 필요한 `deploy` 파일이 있어야 합니다. [서버 checkout](../../shared/docs/operations/checkout.md)을 참고하세요.

이 구성은 단일 worker의 로컬 디스크에 의존하므로 HA가 아닙니다. PostgreSQL 외부 백업을 별도로 준비합니다.

## 실행 호스트 준비

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

## 1. Worker 디스크·포트 준비

원본에 지정한 worker에서 관리자 권한으로 수행합니다.

```bash
sudo install -d -m 0700 /appdata/keycloak-postgres
df -h /appdata/keycloak-postgres
sudo ss -lntp | grep -E ':(80|443)[[:space:]]' || true
```

디스크 공간과 80/443 포트 충돌을 확인합니다. 원격 worker 작업 권한이 없다면 node 관리 담당자가 수행해야 합니다.

## 2. env·DNS·인증서 준비

```text
deploy/keycloak/env/prod.env                   # 서버 설정·credential
deploy/shared/certs/etch-sso.samsungds.net/     # fullchain.crt, private.key
```

[env 안내](02-environment.md)의 서버 기동용 네 항목을 입력합니다.
서버 기동에는 사내·Portal client secret이 필요하지 않습니다.

공개 URL은 경로와 끝의 `/`가 없는 HTTPS URL이어야 하며 Ingress 도메인·인증서 SAN과 맞아야 합니다.
DNS·APP VIP는 [네트워크 정보](../../shared/docs/infrastructure/network.md), 인증서 준비는 [TLS 안내](03-tls.md)를 따릅니다.

인증서 파일을 배치한 뒤 [공용 TLS 등록](../../shared/docs/certificates/apply.md#2-2-kubernetes-tls-secret에-등록-또는-갱신)을 수행합니다.

```bash
make ingress-tls-up KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" TLS_HOST=etch-sso.samsungds.net \
  TLS_CERT_FILE="$PWD/deploy/shared/certs/etch-sso.samsungds.net/fullchain.crt" \
  TLS_KEY_FILE="$PWD/deploy/shared/certs/etch-sso.samsungds.net/private.key"
```

Keycloak 배포는 등록된 인증서를 검사하며 기본적으로 인증서 파일을 다시 읽거나 갱신하지 않습니다.

```bash
vi deploy/keycloak/env/prod.env
chmod 600 deploy/keycloak/env/prod.env
make env-check APP=keycloak PROFILE=prod COMPONENT=server
```

서버 원본만 검사하려면 `make server-check APP=keycloak PROFILE=prod`를 사용합니다.
이 정적 검사는 실제 credential·클러스터 연결·worker 디스크 상태를 검증하지 않습니다.

**완료 기준:** 위 준비 항목과 실행 입력을 확인했습니다. 같은 Bash 터미널에서 [검사·배포](04-deploy.md)로 진행합니다.
