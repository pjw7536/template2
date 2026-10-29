# 클러스터 구성과 상태 확인

[배포 안내](../../../README.md) · [Kubernetes 셋업](../kubernetes/README.md) · [현재 환경 조회](../kubernetes/09-baseline.md)

이 문서는 현재 배포 원본에서 구성 정보를 찾고 대상 서버의 상태를 확인하는 방법을 설명합니다.
노드 목록·Ready 상태·VIP·설치 버전은 대상 클러스터에서 조회합니다.
저장소의 manifest·env는 배포 입력이며 실제 서버에 반영됐다는 증거는 아닙니다.

## 구성별 원본

| 확인할 구성 | 원본·시작 문서 |
| --- | --- |
| 설치할 앱·서버 선택 그룹 | `deploy/shared/apps.json`, [선택 checkout](../../../01-SERVER_CHECKOUT.md) |
| 제어면·Worker·네트워크 설치 기준 | [현재 환경 조회](../kubernetes/09-baseline.md), [제어면 셋업](../kubernetes/01-control-plane.md), [Worker 추가](../kubernetes/03-worker.md) |
| 외부 HTTPS·도메인·VIP 연결 | `deploy/shared/ingress/stack.yaml`, [공용 Ingress](../../ingress/README.md) |
| Keycloak·전용 PostgreSQL | `deploy/keycloak/k8s/server/stack.yaml`, [Keycloak 설치](../../../keycloak/README.md) |
| Portal API·Web·migration | `deploy/portal/k8s`, [Portal 배포](../../../portal/README.md) |
| Airflow·로그·ODBC·DB | `deploy/airflow/helm`, [Airflow 배포](../../../airflow/README.md) |
| MinIO 배치·스토리지 | `deploy/minio/k8s`, [MinIO 배포](../../../minio/README.md) |
| 지표·운영 UI·FTP | [Monitoring](../../../monitoring/README.md), [Headlamp](../../../headlamp/README.md), [FTP](../../../ftp/README.md) |
| 인증서·CA | [인증서 관리](../../certs/README.md) |

노드 배치는 각 앱의 `nodeSelector`·affinity·env, 저장공간은 PV·PVC·Helm values와 비교합니다.
공용 진입점이 여러 Worker에 있어도 앱·DB가 자동 복제되지는 않습니다.

## 현재 상태 조회

배포 호스트의 저장소 루트에서 대상 context를 명시합니다. 아래 명령은 조회만 수행합니다.

```bash
read -r -p '대상 Kubernetes context: ' KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
kubectl --context "$KUBE_CONTEXT" get pods -A -o wide
kubectl --context "$KUBE_CONTEXT" get ingress -A
kubectl --context "$KUBE_CONTEXT" get storageclass
kubectl --context "$KUBE_CONTEXT" get pv
kubectl --context "$KUBE_CONTEXT" get pvc -A
```

기대한 노드 배치와 실제 Pod 위치, PV·PVC 연결을 비교합니다.
Ingress·Pod 상태 확인 뒤 [접속·기능 검증](../kubernetes/06-verification.md)으로 실제 HTTPS·로그인·업무 동작을 확인합니다.
설치 버전·OS·런타임·CNI·VIP는 [환경 조회 안내](../kubernetes/09-baseline.md)에서 별도로 확인합니다.
