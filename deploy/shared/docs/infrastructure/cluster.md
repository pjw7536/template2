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

## 확인된 Worker 설치 기준

확인일은 **2026-10-30**, 근거는 사용자가 제공한 CP1의 버전 명령과 `kubectl get nodes -o wide` 결과입니다.
Worker의 OS도 CP1과 같다는 사용자 확인을 반영했습니다. 아래 값은 조회한 CP1 기준이며
다른 제어면·Worker·API server의 버전까지 일괄 검증한 결과는 아닙니다.

| 항목 | 확인값 | 근거 |
| --- | --- | --- |
| CP1 노드 | `khplane01w06`, `Ready`, `control-plane` | 노드 조회 |
| OS | Ubuntu 22.04.2 LTS (Jammy) | CP1 `/etc/os-release`, Worker는 동일 OS라는 사용자 확인 |
| CP1 아키텍처 | `x86_64` / amd64 | CP1 `uname -m` |
| kubeadm·kubelet | `v1.36.0` | CP1 버전 명령과 노드 조회 |
| containerd | `2.2.1` | CP1 버전 명령과 노드 조회 |
| CP1 커널 | `5.15.0-60-generic` | 노드 조회; 새 Worker 커널의 고정 설치값은 아님 |

[Worker 설치 절차](../kubernetes/03-worker.md#2-빈-서버에-프로그램-설치설정--새-worker)는
새 Ubuntu 22.04 amd64 서버에서 사내 패키지·이미지 미러로 Kubernetes 1.36.0과 containerd 2.2.1을 설치하도록 작성했습니다.
실제 Worker 아키텍처, CNI·MTU·통신 포트, 기존 cgroup 설정, 패키지·이미지 미러와 CA·인증,
사내 미러 접근 여부, 가입 endpoint와 API VIP의 관계는 인프라 담당자와 추가 확인합니다.
확인한 담당자 이름은 제공되지 않았습니다. 네트워크 주소는 실제 가입 명령과 운영 설정을 기준으로 사용합니다.

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
