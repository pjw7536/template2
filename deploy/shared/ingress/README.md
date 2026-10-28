# 공용 Ingress 진입점

[배포 문서 안내](../../README.md)

이 폴더에서 여러 앱이 함께 사용하는 Traefik 설정을 관리합니다.
기본 실행 위치는 기존 `etch-sso` namespace, `khplane01w09` worker이며 80/443을 사용합니다.
현재 APP VIP 환경은 [두 Worker 443 연결 안내](VIP.md)에 따라 동일 Deployment를 두 replica로 확장합니다.
새 Worker를 추가하거나 앱 재배포 없이 Traefik만 확장할 때는 [Worker 추가 가이드](ADD_WORKER.md)를 따릅니다.

## 앱과 독립적으로 준비하기

기존 클러스터에서 앱을 올리기 전에 공용 진입점만 준비할 수 있습니다.
[선택 checkout](../../SERVER_CHECKOUT.md)의 `platform`으로 Portal 외 앱을 준비한 뒤 루트에서 실행합니다.

```bash
read -r -p '대상 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
make ingress-check KUBE_CONTEXT="$KUBE_CONTEXT"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

이 명령은 `deploy/shared`와 루트 Makefile만 사용합니다. 앱 env·이미지 빌드 소스·local 파일을 읽지 않습니다.
`ingress-check`는 공통 원본·노드·선언된 포트 충돌을 검사하고 적용하지 않습니다.
`ingress-up`은 필요한 namespace와 공용 리소스를 적용하며 Keycloak·DB·다른 앱을 재배포하지 않습니다.
OS 프로세스의 80/443 점유와 실제 VIP·HTTPS 응답은 별도로 확인합니다.

최초 VIP 배치를 지정하거나 Backend를 추가할 때는 `VIP_BACKENDS`에 유지할 기존 Worker IP도 모두 포함합니다.
같은 값을 검사·적용 명령에 전달합니다. 입력과 노드 검증은 아래 공통 VIP 규칙을 따릅니다.

```bash
make ingress-check KUBE_CONTEXT="$KUBE_CONTEXT" VIP_BACKENDS="$VIP_BACKENDS"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT" VIP_BACKENDS="$VIP_BACKENDS"
```

### 기존 배치를 보존하는 방법과 검사 범위

기존 controller가 있으면 감시 namespace·replica·전략·nodeSelector·affinity·toleration·topologySpreadConstraints·VIP annotation을 보존합니다.
보존한 배치 정책이 참조하는 Pod label·annotation도 유지하며, 현재 resourceVersion으로 동시 변경을 검사합니다.
Backend 인자를 생략하면 기존 배치를 다시 계산하지 않고 실제 보존할 배치를 검사합니다.
기록된 Backend를 현재 selector·필수 nodeAffinity가 제외하거나 replica가 전체 대상 Worker를 덮지 못하면 적용 전에 중단합니다.
`VIP_BACKENDS`를 명시하면 기존 Backend 제거를 차단한 뒤 각 Backend에 하나씩 배치하도록 다시 계산합니다.

일반 Worker pool에서는 Ready·cordon·taint/toleration·필수 nodeAffinity·80/443 점유를 검사해 사용 가능한 후보를 추립니다.
일부 Worker가 사용 불가능해도 replica 수만큼 서로 다른 후보가 남으면 통과합니다.
필수 nodeAffinity의 label 연산자 `In`, `NotIn`, `Exists`, `DoesNotExist`, `Gt`, `Lt`와 `metadata.name`의 `In`·`NotIn`을 지원합니다.
필수 조건은 [Kubernetes node affinity 규칙](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#node-affinity)의 term 간 OR·term 내부 AND로 검사합니다.
preferred affinity·Pod 간 affinity/anti-affinity·topology spread·리소스 부족 등 전체 scheduler 판단은 모사하지 않으므로 최종 배치는 rollout 결과로 확인합니다.

### 나중에 Portal 연결

Portal은 나중에 checkout을 `all`로 확장하고 [Portal overlay](../../portal/k8s/overlays/prod/README.md)를 적용한 뒤 연결합니다.

```bash
make ingress-connect APP=portal KUBE_CONTEXT="$KUBE_CONTEXT"
```

이 명령은 Portal이 소유한 기존 RBAC를 확인하고 감시 인자만 JSON Patch로 확장합니다.
동시 변경은 resourceVersion으로 검사하며 이미 연결됐거나 전체 namespace를 감시하면 변경하지 않습니다.

## 운영 Ingress 기준

인증서는 `etch-sso/traefik-tls` Secret 한 곳에 보관합니다. 업무 도메인과 SSO 도메인의
인증서를 함께 등록하면 Traefik이 접속 도메인(SNI)에 맞는 인증서를 선택합니다.
앱 Ingress에는 `websecure`, `router.tls=true`만 선언하며 `spec.tls.secretName`을 지정하지 않습니다.

| namespace | Ingress | 공개 주소 |
| --- | --- | --- |
| etch-sso | keycloak | etch-sso.samsungds.net/ |
| tailwind-internal | portal | etch.samsungds.net/ (`/api`, `/auth` 포함) |
| minio | minio-api, minio-console | etch.samsungds.net/minio/, /minio-console/ |
| airflow | airflow-ingress | etch.samsungds.net/airflow |
| headlamp | headlamp | etch.samsungds.net/headlamp/ |
| monitoring | Grafana, Prometheus, Alertmanager | etch.samsungds.net/grafana/, /prometheus/, /alertmanager/ |

### 인증서 최초 등록과 갱신

저장소 루트에서 실행합니다. `TLS_HOST`는 앱의 공개 host와 같아야 합니다.
서버 인증서가 먼저, 중간 CA가 뒤인 fullchain과 짝이 맞는 PEM 개인키를 사용합니다.

```bash
make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST=etch.samsungds.net \
  TLS_CERT_FILE="$PWD/deploy/shared/certs/etch.samsungds.net/fullchain.crt" \
  TLS_KEY_FILE="$PWD/deploy/shared/certs/etch.samsungds.net/private.key"

make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST=etch-sso.samsungds.net \
  TLS_CERT_FILE="$PWD/deploy/shared/certs/etch-sso.samsungds.net/fullchain.crt" \
  TLS_KEY_FILE="$PWD/deploy/shared/certs/etch-sso.samsungds.net/private.key"

make ingress-check KUBE_CONTEXT="$KUBE_CONTEXT"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

MinIO만 설치할 때는 업무 도메인 인증서만 등록해도 됩니다. SSO 설치 시 SSO 인증서를 추가합니다.
갱신도 같은 명령에 새 파일을 전달합니다. 다른 도메인 인증서와 Secret metadata는 보존합니다.
도구는 도메인·만료·키 일치를 검사하고 동시 변경이 있으면 덮어쓰지 않고 실패합니다.
기존 Traefik이 있으면 재시작 후 rollout을 기다립니다. 앱별 인증서 복사·재배포는 필요하지 않습니다.
새 인증서의 신뢰 체인과 실제 VIP 응답은 아래 절차로 별도 확인합니다.

### 기존 설치에서 이전

먼저 기존 유효한 인증서를 공용 저장소로 가져옵니다. 원본 Secret은 변경하지 않습니다.
업무 도메인 원본은 `headlamp/headlamp-tls` 대신 기존 `minio/minio-tls`,
`tailwind-internal/portal-tls`, `airflow/airflow-tls` 등 실제 보유한 것을 사용할 수 있습니다.

```bash
make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST=etch.samsungds.net \
  TLS_SOURCE=headlamp/headlamp-tls
make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST=etch-sso.samsungds.net \
  TLS_SOURCE=etch-sso/keycloak-tls
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

이후 사용하는 앱만 앱별 배포 명령으로 재배포해 기존 Ingress의 `spec.tls.secretName`을 제거합니다.
Portal은 prod overlay를 다시 적용한 후 `make ingress-connect APP=portal`을 실행합니다.
기존 앱별 TLS Secret은 자동 삭제하지 않습니다. 모든 Ingress 참조가 제거되고 HTTPS를 검증한 뒤
운영자가 정리합니다. 이전을 마치기 전에는 기존 Secret도 유지해야 합니다.
기존 Airflow `AIRFLOW_TLS_SOURCE` 입력도 지원하며 이제 공용 저장소에 등록합니다.
앱별 `INGRESS_TLS_SECRET`·`HEADLAMP_TLS_SECRET`은 기존 env 호환용이며 공용 Traefik에서는 사용하지 않습니다.
OIDC CA ConfigMap과 API server의 CA 신뢰 설정은 별도로 유지합니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n etch-sso get secret traefik-tls
kubectl --context "$KUBE_CONTEXT" get ingress -A \
  -o custom-columns='NAMESPACE:.metadata.namespace,NAME:.metadata.name,HOSTS:.spec.rules[*].host,LEGACY_TLS:.spec.tls[*].secretName'
```

인증서는 file provider로 로드하므로 Ingress의 TLS Secret 열이 비어 있는 것이 정상입니다.
실제 인증서는 [인증서 응답 검증](../certs/README.md#2-4-실제-제공되는-인증서-확인)으로 확인합니다.
공식 계약: [Traefik 인증서와 SNI](https://doc.traefik.io/traefik/reference/routing-configuration/http/tls/tls-certificates/),
[file provider](https://doc.traefik.io/traefik/reference/install-configuration/providers/others/file/).

| 파일 | 역할 |
| --- | --- |
| `stack.yaml` | 기존 Traefik ServiceAccount·RBAC·IngressClass·Deployment·Service |
| `kustomization.yaml` | 기존 namespace와 사내 이미지 매핑 |
| `routing.py` | namespace·운영 배치 보존, 정상 Worker 후보·실제 VIP 수용 범위 검사와 앱별 권한 |
| `tls.py` | 공용 TLS 등록·검사·갱신 및 Traefik 재시작 |
| `manage.py` | 앱과 독립적인 검사·적용 및 Portal 후속 연결 진입점 |
| `middlewares` | file provider가 읽는 공용 경로 middleware ConfigMap. 로컬도 같은 정의를 재사용 |
| `VIP.md` | 확정된 APP VIP·업무 DNS·인증서·서버 실행 및 접속 검증 절차 |
| `ADD_WORKER.md` | 새 Worker 등록·Traefik 단독 확장·LB 활성화·검증·복구 절차 |

Keycloak Kustomize 진입점도 이 원본을 참조합니다. 정적 전달 YAML은 `deploy/keycloak/export`에서
운영 설정(2개 replica, RollingUpdate, `etch-sso,headlamp` 감시, `ingress: traefik` 노드 선택)을 추가합니다.
정적 기본값은 `etch-sso` 단독 감시이며 기존 Keycloak 단독 설치와 호환됩니다.

일반 배포에는 [앱별 배포](../docs/kubernetes/05-applications.md)의 명령을 사용합니다.

- `ingress-check/up`: 공용 진입점만 준비하고 기존 감시·배치를 보존합니다.
- `ingress-connect APP=portal`: Portal overlay 적용 후 해당 namespace의 감시만 추가합니다.
- `keycloak-up`: 기존 namespace 감시 범위를 보존합니다.
- `airflow-up`: 자기 namespace의 권한과 감시를 추가합니다.
- `monitoring-up`: 최종 렌더에 공용 Ingress가 있으면 TLS·권한을 검사하고 자기 namespace의 감시를 추가합니다.
- `make server-up`: [서버 기동 안내](../docs/operations/server-start.md)의 기존 통합 운용을 위한 호환 명령입니다.

이 도구들은 기존 Portal 등 다른 namespace를 감시 목록에서 제거하지 않습니다.
이미 전체 namespace를 감시하고 있다면 범위를 좁히지 않습니다.

최초 `VIP_BACKENDS=10.172.40.117,10.172.40.87`을 지정하면 두 IP의 Node를 조회해 각 Worker에 Traefik 하나씩 배치합니다.
Backend 목록은 `deploy.tailwind.local/vip-backends` Deployment annotation에 기록하며 이후 인자를 생략해도 유지합니다.
현재 단독 소스·이미지·hostPort는 그대로 사용하고 앱·DB의 nodeSelector는 변경하지 않습니다.

Airflow는 자기 namespace의 Ingress와 Helm 설정을 소유하며 인증서는 공용 Traefik이 관리합니다.
Portal 전용 Nginx를 거치지 않고 같은 controller가 `/airflow`를 Airflow Service로 전달합니다.
TLS 인증서는 사용 도메인에 맞아야 하며 공용 `etch-sso/traefik-tls`에 등록되어 있어야 합니다.

`kubectl apply -k deploy/shared/ingress`는 단독 기본값을 적용합니다. Keycloak 전달 YAML도 고정된 운영 설정을 적용합니다.
공용 진입점만 갱신할 때는 `ingress-up`, 앱 배포에는 기존 설정을 보존하는 앱별 명령을 사용합니다.

[Traefik Kubernetes Ingress 설정](https://doc.traefik.io/traefik/reference/install-configuration/providers/kubernetes/kubernetes-ingress/)에서 namespace 감시와 IngressClass 동작을 확인할 수 있습니다.

## 하위 경로 middleware

MinIO 콘솔 전용 Ingress는 `minio-console@file`을 참조합니다.
공용 Traefik의 file provider가 `/etc/traefik/dynamic`에 마운트한 ConfigMap을 읽어
`/minio-console`을 `/minio-console/`로 리다이렉트하고, 요청 접두사를 제거해 MinIO:9001로 전달합니다.
콘솔의 WebSocket도 Traefik이 처리합니다. Kubernetes CRD나 추가 RBAC는 필요하지 않습니다.

MinIO만 설치할 때는 [독립 설치 안내](../../minio/README.md)를 따릅니다.
`minio-up`은 Portal 없이 자기 namespace의 권한·감시 범위만 추가합니다.
파일 경로 `/minio/`는 `minio-api@file` middleware로 접두사를 제거하고 MinIO:9000으로 전달합니다.
두 경로 모두 Portal Nginx를 거치지 않습니다.

정규 Keycloak 재배포가 필요한 경우에는 기존 운영 env·인증서·VIP 설정을 유지하는
`make keycloak-up KUBE_CONTEXT="$KUBE_CONTEXT"`이 공용 controller와 ConfigMap도 함께 반영합니다.
이 경우에는 [Keycloak 배포 절차](../../keycloak/README.md)를 따릅니다.
공용 원본을 직접 apply하면 기존 namespace 감시·VIP 배치가 기본값으로 바뀔 수 있으므로 사용하지 않습니다.

로컬은 `make k8s-rebuild APP=portal`이 공용 ConfigMap과 Traefik 설정을 함께 적용합니다. MinIO만 갱신할 때는 `APP=minio`를 사용합니다.

ConfigMap 이름에는 내용 해시가 포함되어 설정 변경 시 Deployment가 새 ConfigMap을 마운트합니다.
앱별 Ingress의 TLS·host와 namespace 감시 범위는 기존 앱 계약을 따릅니다.
로그에 `middleware ... does not exist`가 나오면 file provider 인자와 ConfigMap 마운트 반영 여부를 확인합니다.

공식 참고: [File provider](https://doc.traefik.io/traefik/reference/install-configuration/providers/others/file/),
[StripPrefix](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/stripprefix/).
