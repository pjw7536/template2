# 01. Keycloak 서버 설치와 운영

[시작 안내](README.md) · 다음: [Realm부터 단계별 설정](04_SETUP_FLOW.md) · 입력: [env](env/02_ENVIRONMENT.md) / [TLS](03_TLS.md)

이 문서는 PostgreSQL·Keycloak·Traefik 서버 스택을 준비할 때 사용합니다.
이미 서버가 정상 동작한다면 재설치하지 않고 단계별 설정에서 필요한 작업만 실행합니다.

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
서버 선택 checkout에는 루트 Makefile과 필요한 `deploy` 파일이 있어야 합니다. [서버 checkout](../SERVER_CHECKOUT.md)을 참고하세요.
이 구성은 단일 worker의 로컬 디스크에 의존하므로 HA가 아닙니다. PostgreSQL 외부 백업을 별도로 준비합니다.

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

[env 안내](env/02_ENVIRONMENT.md)의 서버 기동용 네 항목을 입력합니다.
기존 서버라면 실제 DB·관리자 credential을 유지합니다. 서버 기동에는 사내·Portal client secret이 필요하지 않습니다.
공개 URL은 경로와 끝의 `/`가 없는 HTTPS URL이어야 하며 Ingress 도메인·인증서 SAN과 맞아야 합니다.
DNS·APP VIP는 [인프라 현황](../shared/docs/infrastructure/cluster.md), 인증서 준비는 [TLS 안내](03_TLS.md)를 따릅니다.
인증서 파일을 배치하는 것만으로 Secret이나 서버 설정이 바뀌지는 않습니다.

```bash
chmod 600 deploy/keycloak/env/prod.env
make env-check APP=keycloak PROFILE=prod COMPONENT=server
```

서버 원본만 검사하려면 `make server-check APP=keycloak PROFILE=prod`를 사용합니다.
이 정적 검사는 실제 credential·클러스터 연결·worker 디스크 상태를 검증하지 않습니다.

## 3. 검사 후 서버 배포

저장소 루트에서 순서대로 실행합니다. 검사가 실패하면 원인을 해결한 뒤 배포합니다.

```bash
read -r -p '배포할 Kubernetes context: ' KEYCLOAK_KUBE_CONTEXT
make keycloak-check KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
make keycloak-up KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

| 명령 | 처리 범위 |
| --- | --- |
| `keycloak-check` | env·인증서·manifest·기존 Secret·worker 상태를 조회하고 검사 |
| `keycloak-up` | 없는 runtime/TLS Secret 준비, PostgreSQL·Keycloak·Traefik 적용 |

기존 DB/PVC를 삭제하지 않으며 기존 Secret과 입력이 다르면 중단합니다.
기존 PVC는 있는데 runtime Secret만 없다면 실제 DB credential로 Secret을 먼저 복원해야 합니다.
초기 관리자 항목은 빈 DB 최초 기동 시 계정을 만들고, 이후 설정 Job도 같은 Secret으로 로그인합니다.
운영 중 관리자 비밀번호를 바꿨다면 실제 값과 Secret을 맞춥니다.

| 선택 입력 | 사용하는 경우 |
| --- | --- |
| `KEYCLOAK_ENV=/절대/경로/prod.env` | 다른 env 파일 사용 |
| `KEYCLOAK_CERTS=/인증서/폴더` | 다른 TLS 파일 위치 사용 |
| `VIP_BACKENDS=...` | VIP 최초 배치 지정. 검사·배포 양쪽에 동일하게 전달 |

현재 인프라의 VIP 최초 배치 예시는 `10.172.40.117,10.172.40.87`입니다. 실제 운영 대상과 일치하는지 확인합니다.
재적용 시에는 기존 VIP와 다른 앱의 namespace 감시 범위를 보존합니다.

## 4. 서버 기동 확인

```bash
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" get pv keycloak-postgres-data
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get pvc keycloak-postgres-data
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso rollout status statefulset/keycloak-postgres --timeout=5m
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso rollout status deployment/keycloak --timeout=10m
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso rollout status deployment/traefik --timeout=5m
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get pods -o wide
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get ingress
```

Keycloak·PostgreSQL이 원본의 worker에 배치됐는지 확인합니다. Traefik은 VIP·배포 방식에 따라 여러 노드에 배치될 수 있습니다.
외부 DNS/TLS 준비 후 공개 주소의 로그인 화면과 realm discovery 응답을 확인합니다.

```bash
curl -fsS https://etch-sso.samsungds.net/realms/etch/.well-known/openid-configuration
```

실패하면 event·로그로 원인을 확인합니다. 이미지 pull, worker 파일 권한·디스크, 실제 외부 접속은 서버에서 확인해야 합니다.

```bash
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get events --sort-by=.lastTimestamp
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs statefulset/keycloak-postgres
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs deployment/keycloak
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs deployment/traefik
```

## 5. 다음 작업

서버 배포는 관리 스크립트 ConfigMap을 준비하지만 설정 Job은 실행하지 않습니다.
[0~5단계 설정](04_SETUP_FLOW.md)으로 이동합니다. 최초 import가 `etch`를 만들었다면 0번은 기존 realm을 확인하고 무변경 종료합니다.
`etch-realm.json`을 수정하거나 서버를 재배포해도 기존 realm은 자동으로 덮어쓰지 않습니다.

일반 재배포와 빈 DB 재설치는 다릅니다. 데이터 삭제가 필요한 재설치는 [별도 절차](../shared/docs/operations/keycloak-fresh-start.md)에서 다룹니다.
Airflow 연결은 [Airflow 안내](../airflow/README.md)의 전용 배포 흐름을 사용합니다.

## 참고: 수동 YAML 전달 방식

앱 배포 도구를 사용할 수 없는 전달 환경에서만 선택하는 대체 경로입니다. 기본 배포와 반복 실행할 필요는 없습니다.
원본 수정 후 `make k8s-export`로 다음 파일을 만듭니다. 직접 편집하지 않습니다.

| 파일 | 적용 내용 |
| --- | --- |
| `rendered/internal-keycloak-stack.yaml` | 서버·관리 ConfigMap·운영 Traefik |
| `rendered/internal-keycloak-claim-mappers.yaml` | 프로필·IdP mapper 통합 Job과 ConfigMap |

이 파일만 전달하면 0~5단계 실행 파일과 discovery 해석기까지 전달되는 것은 아닙니다.
운영 전달 스택은 Traefik 2 replica, `maxSurge: 0`/`maxUnavailable: 1`, `ingress: traefik` 노드 선택,
`etch-sso,headlamp` 감시를 사용합니다. 기존 Headlamp RBAC와 배치 가능한 라벨 노드 2개가 필요합니다.
hostPort 때문에 두 Pod는 서로 다른 노드에 배치됩니다. 기본 `k8s/` 원본은 이 설정과 다릅니다.
전달 스택을 그대로 적용하면 명시하지 않은 다른 namespace 감시가 해제될 수 있으므로 공유 운영 환경은 `keycloak-up`을 사용합니다.

수동으로 진행할 때는 namespace, runtime Secret, TLS Secret을 먼저 준비하고 스택을 적용합니다.
공통 env 명령은 현재 kubectl context를 사용하므로 선택한 context와 같은지 확인합니다.

```bash
(
  set -e
  test "$(kubectl config current-context)" = "$KEYCLOAK_KUBE_CONTEXT"
  kubectl --context "$KEYCLOAK_KUBE_CONTEXT" create namespace etch-sso --dry-run=client -o yaml | kubectl --context "$KEYCLOAK_KUBE_CONTEXT" apply -f -
  make k8s-env APP=keycloak PROFILE=prod COMPONENT=server
  kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso create secret tls keycloak-tls --cert=deploy/shared/certs/etch-sso.samsungds.net/fullchain.crt --key=deploy/shared/certs/etch-sso.samsungds.net/private.key --dry-run=client -o yaml | kubectl --context "$KEYCLOAK_KUBE_CONTEXT" apply -f -
  kubectl --context "$KEYCLOAK_KUBE_CONTEXT" apply -f deploy/keycloak/rendered/internal-keycloak-stack.yaml
)
```

기존 Secret 갱신은 실제 DB·관리자 비밀번호와 일치하는 경우에만 수행합니다. 사이트 인증서 갱신은 [TLS 안내](03_TLS.md)를 따릅니다.
서버 이후의 설정은 [단계별 실행](04_SETUP_FLOW.md), 원본 관리 방식은 [k8s 안내](k8s/08_KUBERNETES.md)를 참고합니다.
