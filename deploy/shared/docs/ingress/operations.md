# 공용 Ingress 운영 기준

[가이드 홈](../README.md#https인증서) · [ingress 가이드](../../ingress/README.md) · [Traefik 셋업](setup.md) · [Traefik·VIP 확장](expand.md)

여러 앱이 함께 사용하는 공용 Traefik(카탈로그 앱 `ingress`)의 배치 보존·TLS·도메인 라우팅·namespace 감시 계약입니다.
설치·갱신·확인은 [ingress 가이드](../../ingress/README.md), backend를 지정한 설치는 [Traefik 셋업](setup.md), 운영 중 backend 추가는 [Traefik·VIP 확장](expand.md)을 따릅니다.
아래 Make 명령은 관리 호스트의 저장소 루트에서 `KUBE_CONTEXT="<context>"`를 지정해 실행합니다.

## 현재 선언

- 저장소 기본값([`stack.yaml`](../../ingress/stack.yaml)): `etch-sso` namespace, `traefik` Deployment 1 replica, `khplane01w09` 노드, hostPort 80/443.
- VIP backend별 배치는 저장소가 아닌 Deployment의 `deploy.tailwind.local/vip-backends` annotation에 기록됩니다. 실제 replica·배치는 [확장 절차](expand.md#1-현재-배치-조회--관리-호스트)로 조회합니다.
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
하나의 SAN 인증서를 공유하더라도 실제 사용하는 host별로 등록합니다. 앱의 `make ops-deploy`가 준비 검사에서 host마다 자동으로 등록하고, 직접 등록·갱신은 [공용 TLS 등록](../../../README.md#공용-tls-등록)을 따릅니다.

| namespace | Ingress | 공개 주소 |
| --- | --- | --- |
| etch-sso | keycloak | sso.etch.samsungds.net/ |
| tailwind-internal | portal | etch.samsungds.net/ (`/api`, `/auth` 포함) |
| minio | minio-api, minio-console | s3.etch.samsungds.net/, minio.etch.samsungds.net/ |
| airflow | airflow-ingress | airflow.etch.samsungds.net/ |
| headlamp | headlamp | headlamp.etch.samsungds.net/ |
| monitoring | Grafana, Prometheus, Alertmanager | grafana.etch.samsungds.net/, prometheus.etch.samsungds.net/, alert.etch.samsungds.net/ |
| registry | registry | store.etch.samsungds.net/ |

위 표는 저장소 Ingress 선언입니다. 실제 DNS·인증서 적용 상태는 [서비스 원본](../infrastructure/services.md)을 따릅니다.

- 운영 앱은 서비스별 도메인의 `/`를 그대로 전달하며 StripPrefix나 하위 경로 리다이렉트를 사용하지 않습니다.
- Airflow는 자기 namespace의 Ingress와 Helm 설정을 소유합니다. Portal 전용 Nginx를 거치지 않고 같은 controller가 Airflow 도메인의 `/`를 Airflow Service로 전달합니다.
- MinIO는 S3 도메인에서 9000, 콘솔 도메인에서 9001 포트로 전달하며 콘솔 WebSocket도 Traefik이 처리합니다.
- `middlewares/paths.yaml`은 운영 Ingress가 참조하지 않습니다. 공용 file provider는 TLS 인증서 로딩에 사용합니다.

## 앱 namespace 연결

일반 배포에는 [앱별 배포](../../../README.md#앱-설치-순서)의 `make ops-deploy APP=<app> KUBE_CONTEXT="<context>"`를 사용합니다. 앱은 자기 `<app>-up` 안에서 자기 namespace를 감시 목록에 더합니다. 이 도구들은 다른 namespace를 감시 목록에서 제거하지 않으며, 이미 전체 namespace를 감시하면 범위를 좁히지 않습니다.

| 명령 | 공용 Ingress에 주는 영향 |
| --- | --- |
| `ingress-check` / `ingress-up` | 공용 진입점만 검사·준비. 기존 감시·배치 보존 |
| `ingress-connect APP=portal` | Portal overlay가 만든 권한을 확인한 뒤 Portal namespace 감시만 추가. `portal-up`이 배포의 마지막에 같은 연결을 수행 |
| `keycloak-up` | Traefik을 적용하거나 바꾸지 않음. Traefik이 있는지와 공용 TLS를 읽는지만 확인. `KEYCLOAK_CERTS=<폴더>`로 인증서를 함께 등록할 때만 Traefik이 인증서를 다시 읽도록 재시작 |
| `airflow-up`, `headlamp-up`, `registry-up` | 공용 TLS 검사, 자기 namespace의 권한과 감시 추가 |
| `minio-up` | 두 host의 TLS 검사, 자기 namespace의 권한·감시 추가 |
| `monitoring-up` | 최종 렌더에 공용 Ingress가 있으면 TLS·권한 검사, 자기 namespace 감시 추가 |

감시 연결은 Portal만 별도 명령이 있습니다. Portal의 감시 연결만 다시 해야 할 때 씁니다.

[변경] Portal namespace의 감시를 연결합니다. 감시 인자가 바뀌면 Traefik Pod가 다시 시작됩니다.

```bash
make ingress-connect APP=portal KUBE_CONTEXT="<context>"
```

**기대 결과:** `Portal Ingress 연결 완료. 기존 앱과 Portal 접속을 확인하세요.` 또는 `Portal namespace를 이미 감시합니다. 변경하지 않았습니다.`가 출력됩니다.
Portal이 소유한 기존 RBAC를 확인하고 감시 인자만 JSON Patch로 확장합니다. 동시 변경은 resourceVersion으로 검사하며, 이미 연결됐거나 전체 namespace를 감시하면 변경하지 않습니다.
`Portal 라우팅 권한이 부족합니다. Portal overlay를 먼저 적용하세요.`로 끝나면 Portal이 아직 배포되지 않은 것이므로 [Portal 가이드](../../../portal/README.md)의 배포를 먼저 수행합니다.

namespace 감시와 IngressClass 동작은 [Traefik Kubernetes Ingress 설정](https://doc.traefik.io/traefik/reference/install-configuration/providers/kubernetes/kubernetes-ingress/)을 참고합니다.

## 적용 명령과 주의

- [변경] ConfigMap·TLS 마운트를 포함한 공용 설정의 설치·갱신은 `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"`입니다(준비 검사 → `ingress-check` → `ingress-up` → `ingress-smoke` → 대조). 감시 namespace와 현재 배치를 보존합니다.
- [승인] backend 노드의 추가·변경은 같은 명령과 `make ingress-check`에 `VIP_BACKENDS=<IP 목록>`을 붙이며 [Traefik·VIP 확장](expand.md)의 백업·검증 순서를 따릅니다. `VIP_BACKENDS`는 `ingress`에만 쓰는 입력입니다.
- [변경] 인증서는 `make ingress-tls-up`([공용 TLS 등록](../../../README.md#공용-tls-등록)) 또는 앱 배포의 자동 등록으로 적용하고, 앱 배포는 기존 설정을 보존하는 앱별 명령으로 적용합니다.
- `kubectl apply -k deploy/shared/ingress`를 사용하지 않습니다. 단일 Worker·`etch-sso` 단독 감시 기본값이 적용되어 앱 연결·VIP 배치가 바뀝니다.
- `make keycloak-up`은 공용 Traefik을 배포하지 않습니다. Traefik이 없으면 `공용 Traefik이 없습니다. make ops-deploy APP=ingress를 먼저 실행하세요.`로 멈춥니다.
