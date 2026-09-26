# APP VIP로 Keycloak과 Airflow 연결

[공용 Ingress 안내](README.md) · [입문 가이드](../docs/kubernetes/README.md)

처음 배포할 때는 [앱별 순서](../docs/kubernetes/05-applications.md)를 따릅니다.
이 문서 3절의 `server-up`은 이미 Keycloak이 있는 환경의 통합 운용을 위한 호환 경로입니다.
아래 TCP 전달·TLS 종료는 목표 구성이며 실제 LB 설정은 인프라 담당자와 대조합니다.

현재 인프라팀에 등록한 값은 다음과 같습니다.

| 항목 | 값 |
| --- | --- |
| APP VIP | `10.172.26.150:443` |
| 업무 DNS | `etch.samsungds.net` → `10.172.26.150` |
| Backend | `10.172.40.117:443`, `10.172.40.87:443` |
| 전달 방식 | TCP 전달, TLS는 Traefik에서 종료 |
| Airflow URL | `https://etch.samsungds.net/airflow` |
| Keycloak URL | 기존 `https://etch-sso.samsungds.net` 유지 |

VIP는 인프라팀의 네트워크 입구이며 SSH·Git clone·인증서 설치 대상이 아닙니다.
명령은 **기존 클러스터를 관리하는 CP1 등 배포용 checkout**에서 실행합니다.

```text
etch.samsungds.net → APP VIP:443
                         ├─ 10.172.40.117:443 → Traefik ─┐
                         └─ 10.172.40.87:443  → Traefik ─┤
                                                       ├─ /airflow → Airflow
                                                       └─ Keycloak 도메인 → Keycloak
```

두 Worker에는 Traefik을 하나씩 배치합니다. 기존 Keycloak·Airflow·DB는 기존 앱 Worker에 유지합니다.
NodePort는 사용하지 않으며 현재 LB Backend 포트를 변경할 필요가 없습니다.
VIP에서 TLS 종료·PROXY protocol을 별도로 켜지 않습니다. 사용하려면 Traefik 설정과 함께 변경해야 합니다.

## 1. 노드와 포트 확인

```bash
kubectl config get-contexts
read -r -p '배포할 context: ' AIRFLOW_KUBE_CONTEXT
kubectl --context "$AIRFLOW_KUBE_CONTEXT" get nodes -o wide
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n etch-sso get pods -o wide
```

두 Backend IP가 위 Node 목록의 InternalIP로 존재해야 합니다.
두 Worker 모두 같은 Traefik 이미지를 가져올 수 있고 CNI를 통해 앱 Pod에 접근할 수 있어야 합니다.
도구는 Node Ready·cordon·차단 taint·다른 Pod의 선언된 hostPort 충돌을 검사합니다.
OS에서 별도로 실행하는 Nginx 등은 이 검사에 나타나지 않으므로 Worker 담당자가 80/443 점유도 확인합니다.
호스트 프로세스 점검 예: `sudo ss -ltnp '( sport = :80 or sport = :443 )'`.
hostPort 자체는 네트워크 규칙으로 구현될 수 있으므로 ss 결과만으로 Traefik 접속 여부를 판단하지 않습니다.

인프라팀에는 두 Backend에 대한 **TCP 443 Health Check**와 DOWN Backend 제외가 설정되어 있는지 확인합니다.
TCP 검사는 포트 연결만 검사하므로 실제 앱 확인은 아래 HTTPS 검사로 별도 수행합니다.

## 2. Airflow 최초 준비와 업무 도메인 인증서 등록

[서버 기동 안내](../docs/operations/server-start.md)의 Airflow env·이미지·차트·worker 디스크 준비를 먼저 수행합니다.
실제 `deploy/airflow/env/k8s.env`에는 다음 값을 입력합니다. 기존 비밀값과 다른 설정은 유지합니다.

```dotenv
INGRESS_ENABLED=true
INGRESS_CLASS_NAME=traefik
INGRESS_TLS_SECRET=airflow-tls
AIRFLOW_WEBSERVER_BASE_URL=https://etch.samsungds.net/airflow
```

`NODE_NAME`은 기존 앱 Worker의 hostname label입니다. 두 ingress Worker 목록이나 VIP를 넣지 않습니다.
`etch.samsungds.net`을 포함하는 사내 인증서·개인키를 준비합니다. 기존 Keycloak 인증서는 그대로 둡니다.
인증서·키를 Git에 넣지 않습니다. 인증서 파일은 서버의 실제 경로를 입력합니다.

```bash
read -r -p '인증서 전체 체인 파일: ' ETCH_CERT_PATH
read -r -p '인증서 개인키 파일: ' ETCH_KEY_PATH
openssl x509 -in "$ETCH_CERT_PATH" -noout -checkhost etch.samsungds.net
openssl x509 -in "$ETCH_CERT_PATH" -noout -checkend 0

# 최초 namespace와 TLS Secret이 없을 때 실행합니다. NAMESPACE를 바꿨다면 명령에도 반영합니다.
kubectl --context "$AIRFLOW_KUBE_CONTEXT" create namespace airflow
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow create secret tls airflow-tls \
  --cert="$ETCH_CERT_PATH" --key="$ETCH_KEY_PATH"
```

namespace가 이미 있으면 해당 create 명령은 건너뜁니다. 기존 `airflow-tls`가 있다면 먼저 도메인을 확인하고 인증서 교체 절차를 별도로 수행합니다.
기존 `headlamp/headlamp-tls`가 있다면 위 직접 생성 대신 [서버 기동 안내](../docs/operations/server-start.md)의
`AIRFLOW_TLS_SOURCE=headlamp/headlamp-tls` 복사 기능을 사용합니다. 아래 검사 명령에는
`--tls-source headlamp/headlamp-tls`, 배포 명령에는 `AIRFLOW_TLS_SOURCE=headlamp/headlamp-tls`를 추가합니다.

## 3. 검사 후 배포

개발 PC 변경사항이 원격 저장소에 반영된 후 서버 checkout에서 pull합니다.
선택 checkout은 `keycloak-airflow`를 사용합니다. 도구는 기존 Keycloak 스택이 있다고 가정합니다.

```bash
git pull --ff-only
make server-check APP=keycloak-airflow

python3 deploy/shared/scripts/server-up.py \
  --context "$AIRFLOW_KUBE_CONTEXT" \
  --vip-backends 10.172.40.117,10.172.40.87 \
  --check-only

make server-up KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT" \
  VIP_BACKENDS=10.172.40.117,10.172.40.87
```

`--check-only`는 설정·Helm 렌더·기존 리소스·TLS·VIP 배치를 조회하고 검사합니다.
실제 이미지 pull·Pod 스케줄링·DB 접속·VIP 통신을 보장하는 검사는 아닙니다.

기존 Traefik Deployment를 replicas=2로 확장하며 노드별 하나씩 배치합니다.
hostPort 충돌을 피하도록 RollingUpdate는 maxSurge=0, maxUnavailable=1입니다.
신규 DAG는 일시정지로 시작합니다. 기존 DB에서 복원한 활성 DAG는 상태를 별도 확인합니다.

성공한 이후에는 같은 명령을 반복하거나 `VIP_BACKENDS`를 생략할 수 있습니다.
기존 Deployment annotation에 기록한 목록을 읽어 두 Worker 배치를 유지합니다.
정적 Keycloak YAML 직접 apply는 단독 배치로 되돌리므로 사용하지 않습니다.

## 4. 두 Worker와 VIP 각각 HTTPS 확인

```bash
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n etch-sso get pods -l app.kubernetes.io/name=traefik -o wide
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow get pods,pvc,ingress

curl --fail --show-error --resolve etch.samsungds.net:443:10.172.40.117 https://etch.samsungds.net/airflow/health
curl --fail --show-error --resolve etch.samsungds.net:443:10.172.40.87 https://etch.samsungds.net/airflow/health
curl --fail --show-error --resolve etch.samsungds.net:443:10.172.26.150 https://etch.samsungds.net/airflow/health
```

사내 CA가 OS에 없다면 `--cacert /실제/사내-ca.pem`을 지정합니다. `-k`로 인증서 검증을 생략하지 않습니다.
응답의 metadatabase·scheduler 상태가 healthy인지 확인하고 브라우저에서 실제 로그인도 확인합니다.
아직 Portal은 배포하지 않으므로 루트 `/`의 404만으로 Airflow 실패를 판단하지 않습니다.

Keycloak DNS를 바꾸기 전에는 아래처럼 기존 도메인·인증서로 VIP 연결을 먼저 검사합니다.

```bash
curl --show-error --resolve etch-sso.samsungds.net:443:10.172.26.150 -I https://etch-sso.samsungds.net/
```

테스트 PC의 hosts에서만 기존 Keycloak 도메인을 VIP에 연결해 실제 로그인까지 확인한 뒤,
인프라팀에 `etch-sso.samsungds.net → 10.172.26.150` 변경을 요청합니다.
전환 중 기존 Worker:443 접속은 유지됩니다. 도메인·issuer·Keycloak 인증서·DB는 바꾸지 않습니다.

두 ingress Worker를 사용해도 단일 앱·DB Worker 장애는 별도 문제입니다. 현재 단계는 앱 복제나 DB 고가용성을 포함하지 않습니다.

배치 원리는 [Kubernetes Node affinity](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#node-affinity)와
[Deployment RollingUpdate](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-update-deployment)를 따릅니다.
