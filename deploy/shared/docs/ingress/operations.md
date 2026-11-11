# 공용 Ingress 운영 기준

[가이드 홈](../README.md#https인증서) · [Traefik 셋업](setup.md) · [Traefik·VIP 확장](expand.md) · [실행 원본](../../ingress/README.md)

여러 앱이 함께 사용하는 공용 Traefik의 배치 보존·TLS·도메인 라우팅·namespace 감시 계약입니다.
설치·갱신은 [Traefik 셋업](setup.md), 운영 중 backend 추가는 [Traefik·VIP 확장](expand.md)을 따릅니다.
아래 Make 명령은 CP1의 저장소 루트에서 `KUBE_CONTEXT`를 지정해 실행합니다.

## 현재 선언

- 저장소 기본값([`stack.yaml`](../../ingress/stack.yaml)): `etch-sso` namespace, `traefik` Deployment 1 replica, `khplane01w09` 노드, hostPort 80/443.
- VIP backend별 배치는 저장소가 아닌 Deployment의 `deploy.tailwind.local/vip-backends` annotation에 기록됩니다. 실제 replica·배치는 [확장 절차](expand.md#1-현재-배치-조회--cp1)로 조회합니다.
- APP VIP와 backend·노드 대응은 [네트워크 원본](../infrastructure/network.md#vipdns접속-경로)을 따릅니다.

## 배치 보존과 검사 범위

- 기존 controller가 있으면 감시 namespace·replica·전략·nodeSelector·affinity·toleration·topologySpreadConstraints·VIP annotation을 보존합니다.
  보존한 배치 정책이 참조하는 Pod label·annotation도 유지하며 현재 resourceVersion으로 동시 변경을 검사합니다.
- `VIP_BACKENDS`를 생략하면 기존 배치를 다시 계산하지 않고 보존할 배치를 검사합니다. 기록된 backend를 현재 selector·필수 nodeAffinity가 제외하거나 replica가 전체 대상 Worker를 덮지 못하면 적용 전에 중단합니다.
- `VIP_BACKENDS`를 명시하면 기존 backend 제거를 차단한 뒤 각 backend IP의 Node에 Traefik을 하나씩 배치하도록 다시 계산하고 annotation에 기록합니다. 이후 인자를 생략해도 유지됩니다.
- 이미지·hostPort는 그대로 사용하며 앱·DB의 nodeSelector는 변경하지 않습니다.
- 일반 Worker pool에서는 Ready·cordon·taint/toleration·필수 nodeAffinity·80/443 점유를 검사해 후보를 추립니다. replica 수만큼 서로 다른 후보가 남으면 통과합니다.
- 필수 nodeAffinity의 label 연산자 `In`, `NotIn`, `Exists`, `DoesNotExist`, `Gt`, `Lt`와 `metadata.name`의 `In`·`NotIn`을 지원하며,
  [Kubernetes node affinity 규칙](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#node-affinity)의 term 간 OR·term 내부 AND로 검사합니다.
- preferred affinity·Pod 간 affinity/anti-affinity·topology spread·리소스 부족 등 전체 scheduler 판단은 모사하지 않으므로 최종 배치는 rollout 결과로 확인합니다.

## TLS와 도메인 라우팅

인증서는 `etch-sso/traefik-tls` Secret 한 곳에 보관하며 Traefik이 접속 도메인(SNI)에 맞는 인증서를 선택합니다.
앱 Ingress에는 `websecure`, `router.tls=true`만 선언하고 `spec.tls.secretName`을 지정하지 않습니다.
하나의 SAN 인증서를 공유하더라도 실제 사용하는 host별로 [등록·갱신](../certificates/apply.md#2-공용-tls-secret-등록갱신--cp1)합니다.

| namespace | Ingress | 공개 주소 |
| --- | --- | --- |
| etch-sso | keycloak | sso.etch.samsungds.net/ |
| tailwind-internal | portal | etch.samsungds.net/ (`/api`, `/auth` 포함) |
| minio | minio-api, minio-console | s3.etch.samsungds.net/, minio.etch.samsungds.net/ |
| airflow | airflow-ingress | airflow.etch.samsungds.net/ |
| headlamp | headlamp | headlamp.etch.samsungds.net/ |
| monitoring | Grafana, Prometheus, Alertmanager | grafana.etch.samsungds.net/, prometheus.etch.samsungds.net/, alert.etch.samsungds.net/ |

위 표는 저장소 Ingress 선언입니다. 실제 DNS·인증서 적용 상태는 [서비스 원본](../infrastructure/services.md)을 따릅니다.

- 운영 앱은 서비스별 도메인의 `/`를 그대로 전달하며 StripPrefix나 하위 경로 리다이렉트를 사용하지 않습니다.
- Airflow는 자기 namespace의 Ingress와 Helm 설정을 소유합니다. Portal 전용 Nginx를 거치지 않고 같은 controller가 Airflow 도메인의 `/`를 Airflow Service로 전달합니다.
- MinIO는 S3 도메인에서 9000, 콘솔 도메인에서 9001 포트로 전달하며 콘솔 WebSocket도 Traefik이 처리합니다.
- `middlewares/paths.yaml`은 운영 Ingress가 참조하지 않습니다. 공용 file provider는 TLS 인증서 로딩에 사용합니다.

## 앱 namespace 연결

일반 배포에는 [앱별 배포](../operations/02-deploy.md#앱-의존-관계)의 명령을 사용합니다. 이 도구들은 다른 namespace를 감시 목록에서 제거하지 않으며, 이미 전체 namespace를 감시하면 범위를 좁히지 않습니다.

| 명령 | 공용 Ingress에 주는 영향 |
| --- | --- |
| `ingress-check` / `ingress-up` | 공용 진입점만 검사·준비. 기존 감시·배치 보존 |
| `ingress-connect APP=portal` | Portal overlay 적용 후 해당 namespace 감시만 추가 |
| `keycloak-up` | 기존 namespace 감시 범위 보존 |
| `airflow-up` | 자기 namespace의 권한과 감시 추가 |
| `minio-up` | 두 host의 TLS 검사, 자기 namespace의 권한·감시 추가 |
| `monitoring-up` | 최종 렌더에 공용 Ingress가 있으면 TLS·권한 검사, 자기 namespace 감시 추가 |

Portal은 checkout을 `all`로 확장하고 [Portal overlay](../../../portal/k8s/overlays/prod/README.md)를 적용한 뒤 연결합니다.

```bash
make ingress-connect APP=portal KUBE_CONTEXT="$KUBE_CONTEXT"
```

**기대 결과:** Portal이 소유한 기존 RBAC를 확인하고 감시 인자만 JSON Patch로 확장합니다. 동시 변경은 resourceVersion으로 검사하며, 이미 연결됐거나 전체 namespace를 감시하면 변경하지 않습니다.

namespace 감시와 IngressClass 동작은 [Traefik Kubernetes Ingress 설정](https://doc.traefik.io/traefik/reference/install-configuration/providers/kubernetes/kubernetes-ingress/)을 참고합니다.

## 적용 명령과 주의

- ConfigMap·TLS를 포함한 공용 설정 변경은 `make ingress-up`, 인증서는 `make ingress-tls-up`, 앱 배포는 기존 설정을 보존하는 앱별 명령으로 적용합니다.
- `kubectl apply -k deploy/shared/ingress`를 사용하지 않습니다. 단일 Worker·`etch-sso` 단독 감시 기본값이 적용되어 앱 연결·VIP 배치가 바뀝니다.
- Keycloak 정적 전달 YAML(`deploy/keycloak/export`)은 이 원본에 운영 설정(2 replica, RollingUpdate `maxSurge=0`/`maxUnavailable=1`, `etch-sso,headlamp` 감시, `ingress: traefik` 노드 선택)을 고정해 추가합니다.
  VIP annotation 배치와 다른 감시 목록을 덮어쓸 수 있으므로 공유 클러스터에는 직접 적용하지 않습니다. Keycloak Kustomize 기본값은 `etch-sso` 단독 감시이며 기존 Keycloak 단독 설치와 호환됩니다.
- `make server-up`은 Airflow까지 배포하므로 공용 진입점만 바꿀 때는 사용하지 않습니다.
