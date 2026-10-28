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

프로젝트의 서버 가이드에서는 다음 값을 사용합니다. `name`은 Ingress 리소스 이름이며,
`tls_secret`은 해당 행의 namespace에 있는 Secret 이름입니다.

| namespace | name | hosts | tls_secret |
| --- | --- | --- | --- |
| etch-sso | keycloak | etch-sso.samsungds.net | keycloak-tls |
| headlamp | headlamp | etch.samsungds.net | headlamp-tls |

Keycloak은 `https://etch-sso.samsungds.net`, Headlamp는 `https://etch.samsungds.net/headlamp/`로 접속합니다.
Airflow 공개 주소는 `https://etch.samsungds.net/airflow`입니다.
Airflow는 `headlamp/headlamp-tls`의 인증서를 자기 namespace의 `airflow-tls`로 최초 복사해 사용합니다.
Secret은 namespace 간 직접 참조할 수 없으며, 원본 인증서 갱신 시 복사본도 별도로 갱신해야 합니다.

배포 후 대상 context에서 다음 값과 대조합니다.

```bash
kubectl --context "$KUBE_CONTEXT" get ingress -A \
  -o custom-columns='NAMESPACE:.metadata.namespace,NAME:.metadata.name,HOSTS:.spec.tls[*].hosts,TLS_SECRET:.spec.tls[*].secretName'
```

| 파일 | 역할 |
| --- | --- |
| `stack.yaml` | 기존 Traefik ServiceAccount·RBAC·IngressClass·Deployment·Service |
| `kustomization.yaml` | 기존 namespace와 사내 이미지 매핑 |
| `routing.py` | namespace·운영 배치 보존, 정상 Worker 후보·실제 VIP 수용 범위 검사와 앱별 권한 |
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
- `make server-up`: [서버 기동 안내](../docs/operations/server-start.md)의 기존 통합 운용을 위한 호환 명령입니다.

이 도구들은 기존 Portal 등 다른 namespace를 감시 목록에서 제거하지 않습니다.
이미 전체 namespace를 감시하고 있다면 범위를 좁히지 않습니다.

최초 `VIP_BACKENDS=10.172.40.117,10.172.40.87`을 지정하면 두 IP의 Node를 조회해 각 Worker에 Traefik 하나씩 배치합니다.
Backend 목록은 `deploy.tailwind.local/vip-backends` Deployment annotation에 기록하며 이후 인자를 생략해도 유지합니다.
현재 단독 소스·이미지·hostPort는 그대로 사용하고 앱·DB의 nodeSelector는 변경하지 않습니다.

Airflow는 자기 namespace의 Ingress·TLS Secret과 Helm 설정을 소유합니다.
Portal 전용 Nginx를 거치지 않고 같은 controller가 `/airflow`를 Airflow Service로 전달합니다.
TLS는 사용 도메인에 맞는 인증서여야 하며 앱 namespace에 존재해야 합니다.

`kubectl apply -k deploy/shared/ingress`는 단독 기본값을 적용합니다. Keycloak 전달 YAML도 고정된 운영 설정을 적용합니다.
공용 진입점만 갱신할 때는 `ingress-up`, 앱 배포에는 기존 설정을 보존하는 앱별 명령을 사용합니다.

[Traefik Kubernetes Ingress 설정](https://doc.traefik.io/traefik/reference/install-configuration/providers/kubernetes/kubernetes-ingress/)에서 namespace 감시와 IngressClass 동작을 확인할 수 있습니다.

## 하위 경로 middleware

MinIO 콘솔 전용 Ingress는 `minio-console@file`을 참조합니다.
공용 Traefik의 file provider가 `/etc/traefik/dynamic`에 마운트한 ConfigMap을 읽어
`/minio-console`을 `/minio-console/`로 리다이렉트하고, 요청 접두사를 제거해 MinIO:9001로 전달합니다.
콘솔의 WebSocket도 Traefik이 처리합니다. Kubernetes CRD나 추가 RBAC는 필요하지 않습니다.

기존 서버에 MinIO만 추가할 때는 [단독 설치의 Traefik 설정 단계](../../portal/MINIO_SETUP.md#5-공용-traefik에-minio-경로-설정)에 따라
ConfigMap을 생성하고 실행 중인 controller의 file provider·volume·namespace 감시만 수정합니다.
이 절차는 Keycloak·Portal 전체를 재배포하지 않습니다.

정규 Keycloak 재배포가 필요한 경우에는 기존 운영 env·인증서·VIP 설정을 유지하는
`make keycloak-up KUBE_CONTEXT="$KUBE_CONTEXT"`이 공용 controller와 ConfigMap도 함께 반영합니다.
이 경우에는 [Keycloak 배포 절차](../../keycloak/README.md)를 따릅니다.
공용 원본을 직접 apply하면 기존 namespace 감시·VIP 배치가 기본값으로 바뀔 수 있으므로 사용하지 않습니다.

로컬은 `make k8s-rebuild APP=portal`이 공용 ConfigMap과 Traefik 설정을 함께 적용합니다.

ConfigMap 이름에는 내용 해시가 포함되어 설정 변경 시 Deployment가 새 ConfigMap을 마운트합니다.
앱별 Ingress의 TLS·host와 namespace 감시 범위는 기존 앱 계약을 따릅니다.
로그에 `middleware ... does not exist`가 나오면 file provider 인자와 ConfigMap 마운트 반영 여부를 확인합니다.

공식 참고: [File provider](https://doc.traefik.io/traefik/reference/install-configuration/providers/others/file/),
[StripPrefix](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/stripprefix/).
