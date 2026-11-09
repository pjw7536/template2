# 공용 Ingress 운영 기준

[Ingress 안내](../README.md#https인증서) · [배포 문서 안내](../../../README.md) · [실행 원본](../../ingress/README.md)

여러 앱이 함께 사용하는 Traefik 설정의 운영 계약을 설명합니다.
처음 설치할 때는 [Traefik 셋업](setup.md)의 실행 순서로 시작합니다.
이 문서는 namespace 감시·TLS 이전·앱 연결 등 상세 참고입니다.
기본 실행 위치는 기존 `etch-sso` namespace, `khplane01w09` worker이며 80/443을 사용합니다.
현재 APP VIP 환경은 [두 Worker 443 연결 안내](setup.md)에 따라 동일 Deployment를 두 replica로 확장합니다.
클러스터에 서버를 등록할 때는 [Worker 추가](../kubernetes/worker.md),
기존 ingress 배치를 백업하며 확장할 때는 [Traefik·VIP 확장](expand.md)을 따릅니다.

공용 진입점의 최초 설치·대상 선택·검사·적용은 [Traefik 설치](setup.md)를 따릅니다.
이 문서는 기존 운영 배치의 보존 규칙·namespace 감시·middleware 동작을 설명합니다.

## 기존 배치를 보존하는 방법과 검사 범위

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

Portal은 나중에 checkout을 `all`로 확장하고 [Portal overlay](../../../portal/k8s/overlays/prod/README.md)를 적용한 뒤 연결합니다.

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

공용 TLS의 [등록·갱신](../certificates/apply.md#2-2-kubernetes-tls-secret에-등록-또는-갱신)과
[기존 앱 Secret에서 이전](../certificates/apply.md#기존-설치에서-이전)은 인증서 적용 절차를 따릅니다.
manifest·도구·middleware 파일의 역할은 [실행 원본](../../ingress/README.md)에서 확인합니다.

Keycloak Kustomize 진입점도 이 원본을 참조합니다. 정적 전달 YAML은 `deploy/keycloak/export`에서
운영 설정(2개 replica, RollingUpdate, `etch-sso,headlamp` 감시, `ingress: traefik` 노드 선택)을 추가합니다.
정적 기본값은 `etch-sso` 단독 감시이며 기존 Keycloak 단독 설치와 호환됩니다.

일반 배포에는 [앱별 배포](../operations/02-deploy.md#앱-의존-관계)의 명령을 사용합니다.

- `ingress-check/up`: 공용 진입점만 준비하고 기존 감시·배치를 보존합니다.
- `ingress-connect APP=portal`: Portal overlay 적용 후 해당 namespace의 감시만 추가합니다.
- `keycloak-up`: 기존 namespace 감시 범위를 보존합니다.
- `airflow-up`: 자기 namespace의 권한과 감시를 추가합니다.
- `monitoring-up`: 최종 렌더에 공용 Ingress가 있으면 TLS·권한을 검사하고 자기 namespace의 감시를 추가합니다.

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

MinIO만 설치할 때는 [독립 설치 안내](../../../minio/README.md)를 따릅니다.
`minio-up`은 Portal 없이 자기 namespace의 권한·감시 범위만 추가합니다.
파일 경로 `/minio/`는 `minio-api@file` middleware로 접두사를 제거하고 MinIO:9000으로 전달합니다.
두 경로 모두 Portal Nginx를 거치지 않습니다.

정규 Keycloak 재배포가 필요한 경우에는 기존 운영 env·인증서·VIP 설정을 유지하는
`make keycloak-up KUBE_CONTEXT="$KUBE_CONTEXT"`이 공용 controller와 ConfigMap도 함께 반영합니다.
이 경우에는 [Keycloak 배포 절차](../../../keycloak/README.md)를 따릅니다.
공용 원본을 직접 apply하면 기존 namespace 감시·VIP 배치가 기본값으로 바뀔 수 있으므로 사용하지 않습니다.

로컬은 `make k8s-rebuild APP=portal`이 공용 ConfigMap과 Traefik 설정을 함께 적용합니다. MinIO만 갱신할 때는 `APP=minio`를 사용합니다.

ConfigMap 이름에는 내용 해시가 포함되어 설정 변경 시 Deployment가 새 ConfigMap을 마운트합니다.
앱별 Ingress의 TLS·host와 namespace 감시 범위는 기존 앱 계약을 따릅니다.
로그에 `middleware ... does not exist`가 나오면 file provider 인자와 ConfigMap 마운트 반영 여부를 확인합니다.

공식 참고: [File provider](https://doc.traefik.io/traefik/reference/install-configuration/providers/others/file/),
[StripPrefix](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/stripprefix/).
