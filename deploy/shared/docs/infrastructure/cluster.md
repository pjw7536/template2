# 클러스터 구성과 상태 확인

[사내 환경 요약](README.md) · [배포 안내](../../../README.md) · [Kubernetes 셋업](../kubernetes/README.md) · [현재 환경 조회](../kubernetes/09-baseline.md)

이 문서는 현재 배포 원본에서 구성 정보를 찾고 대상 서버의 상태를 확인하는 방법을 설명합니다.
노드 목록·Ready 상태·VIP·설치 버전은 대상 클러스터에서 조회합니다.
저장소의 manifest·env는 배포 입력이며 실제 서버에 반영됐다는 증거는 아닙니다.

**저장소 대조일: 2026-10-30.** 아래 저장소 선언·문서 기록은 이 날짜에 파일을 대조한 결과이며
실제 운영 확인일이 아닙니다. 서버 관측값의 확인일은 해당 절에 따로 표시합니다.
담당자 이름은 제공되지 않아 모두 미확인입니다. 확인 상태와 갱신 규칙은 [환경 요약](README.md#확인-상태를-기록하는-방법)을 따릅니다.

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

## 서버와 노드 목록

| 역할 | 노드명 | InternalIP | 확인 상태·근거 |
| --- | --- | --- | --- |
| CP1·관리 명령 실행 | `khplane01w06` | 미확인 | 2026-10-30 사용자 제공 노드 조회에서 `Ready`, `control-plane`. 버전은 아래 확인 기준 참조 |
| CP2·CP3 | 미확인 | 미확인 | 셋업 가이드의 제어면 3대는 목표 구성. 실제 노드명·대수·Ready는 추가 조회 필요 |
| Keycloak·기본 Traefik 배치 대상 Worker | `khplane01w09` | 미확인 | Keycloak·공용 Ingress 원본의 저장소 선언. 실제 역할·Ready·Pod 배치는 미확인 |
| MinIO 배치 대상 Worker | `khplanew01` | 미확인 | MinIO env·원본의 저장소 선언. 실제 역할·Ready·Pod 배치는 미확인 |

전체 서버 대수와 위 노드 외 추가 Worker는 미확인입니다. 노드 이름으로 역할·IP를 추정하지 않습니다.
CPU·메모리·디스크·마운트·각 노드의 커널과 설치 버전은 [환경 조회](../kubernetes/09-baseline.md)로 확인합니다.

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

## VIP·DNS·클러스터 네트워크

| 항목 | 기록된 값·선언 | 확인 상태·근거 | 남은 확인 |
| --- | --- | --- | --- |
| API VIP | `10.172.26.148:6443` | [제어면 셋업](../kubernetes/01-control-plane.md)의 기존 환경 기록 | 실제 kubeconfig·가입 endpoint와의 일치, LB backend·상태 검사 |
| APP VIP | `10.172.26.150:443` | [Worker 확장](../../ingress/02-ADD_WORKER.md)의 구성도·접속 예시 | 실제 LB 설정, DNS 연결, Worker별 HTTPS 응답 |
| APP VIP backend 후보 | `10.172.40.117`, `10.172.40.87` | [Ingress 안내](../../ingress/README.md)의 최초 배치 예시 | 각 IP의 실제 노드명·InternalIP, 현재 backend 전체 목록. IP와 노드명을 임의로 대응시키지 않음 |
| 업무 DNS | `etch.samsungds.net` | Portal Ingress·MinIO env·Monitoring env·Headlamp env의 저장소 선언 | 실제 DNS 응답·APP VIP 연결·인증서 |
| Keycloak DNS | `etch-sso.samsungds.net` | Keycloak Ingress의 저장소 선언 | 실제 DNS 전환 여부·접속·인증서 |
| HTTPS 경로 | APP VIP → Worker hostPort 443 → 공용 Traefik → 앱 Service | [VIP 절차](../../ingress/01-VIP.md)의 목표 구성. TLS는 Traefik에서 종료 | 실제 TLS 종료 위치, LB의 TCP 전달·PROXY protocol 사용 여부 |
| CNI·Pod/Service CIDR·MTU·DNS domain | 미확인 | 구축 기록·각 노드·시스템 리소스 조회 필요 | 네트워크 담당자 확인, Worker 가입·Pod/Service 통신 검증 |
| etcd·CRI socket·cgroup·registry CA/인증 | 미확인 | CP1의 containerd 버전 확인과는 별도 항목 | 실제 실행 설정과 인증서·권한 확인 |

문서에 주소가 기록되어 있어도 현재 도달 가능하다는 뜻은 아닙니다.
새 검증 환경에는 운영 IP를 재사용하지 않으며 배포 입력에는 확인한 실제 값을 사용합니다.

## 앱별 배치와 스토리지 선언

아래는 저장소에 선언된 값입니다. **실제 설치 여부·Pod 배치·PV 연결·백업 상태는 모두 별도 확인이 필요합니다.**
외부 env를 지정하면 저장소 기본값과 다를 수 있습니다. 선택 checkout에 없는 앱은 해당 앱을 선택한 뒤 원본을 확인합니다.

| 앱·공통 구성 | namespace | 배치 입력 | 스토리지·설정 원본 |
| --- | --- | --- | --- |
| 공용 Traefik | `etch-sso` | 기본 `khplane01w09`. VIP 확장 시 기존 배치를 보존하고 backend별 배치 계산 | `deploy/shared/ingress/stack.yaml`, [Ingress 운영](../../ingress/README.md) |
| Keycloak·전용 PostgreSQL | `etch-sso` | `khplane01w09` | 정적 local PV 50Gi, `/appdata/keycloak-postgres`. `deploy/keycloak/k8s/server/stack.yaml`, [Keycloak 안내](../../../keycloak/README.md) |
| Portal | `tailwind-internal` | 운영 Worker·이미지 미확정 | 외부 PostgreSQL, 공용 MinIO 사용. 업무 파일 기본 `emptyDir`는 운영 PVC로 교체 필요. [prod overlay](../../../portal/k8s/overlays/prod/README.md) |
| MinIO | `minio` | `NODE_NAME=khplanew01` | PVC 10Gi, 기본 정적 모드 `/data/minio`. `deploy/minio/env/prod.env`, [MinIO 안내](../../../minio/README.md) |
| Airflow·전용 PostgreSQL | `airflow` | `NODE_NAME=replace-me-node`로 미확정 | DB `/srv/airflow/postgres` 20Gi, 로그 `/srv/airflow/logs` 20Gi, ODBC `/srv/airflow/odbc`. `deploy/airflow/env/k8s.env`, [Airflow 안내](../../../airflow/README.md) |
| Monitoring | `monitoring` | `NODE_NAME=replace-me-node`로 미확정 | `DATA_HOST_PATH=/srv/monitoring` 아래 local PV. `deploy/monitoring/env/k8s.env`, [Monitoring 안내](../../../monitoring/README.md) |
| Headlamp | `headlamp` | 실제 배치 노드 미확인 | Helm values·`deploy/headlamp/env/k8s.env`로 관리. [Headlamp 안내](../../../headlamp/README.md) |
| FTP | `etch-ftp` | `etch.io/ftp-enabled=true`인 Linux 노드별 DaemonSet | hostPath `/data/data_movement`, 노드 간 자동 복제 없음. `deploy/ftp/k8s/stack.yaml`, [FTP 안내](../../../ftp/README.md) |

공용 진입점의 확장과 앱·DB의 복제 여부를 구분합니다. 특히 local PV·hostPath는 해당 노드의 데이터이며
다른 Worker로 옮길 때 별도 이전·복구가 필요합니다. 자원 용량·replica와 실제 여유는 앱 원본·클러스터에서 확인합니다.

## 운영 파일과 의존성 관리 위치

| 구분 | 관리 위치·계약 | 근거·확인 상태 |
| --- | --- | --- |
| 서버 checkout | `/appdata/etchax` | [선택 checkout](../../../01-SERVER_CHECKOUT.md)의 설치 경로. 현재 서버 경로는 확인 필요 |
| CP1 외부 앱 설정 | `/appdata/etchax-config/<app>/` | [배포 안내](../../../README.md#소유권)의 기존 CP1 설정 기록. 앱 도구에 외부 env 경로 명시 |
| 앱별 기본 env·Secret 입력 | 각 `deploy/<app>/env/`와 앱별 별도 입력 | [환경설정](../configuration/environment.md). 실제 사용 파일·Secret 값은 여기에 복제하지 않음 |
| 인증서·개인키·kubeconfig | Git 밖의 서버 파일·배포 계정 설정 | [인증서 관리](../../certs/README.md), [CP1 운영](../operations/02-cp1.md). 실제 경로·권한 확인 필요 |
| 패키지·이미지 미러 | [미러 원본](01-proxy-mirrors.md) | 저장소 적용 사례와 이름 목록을 구분. CA·인증·권한·실제 접근은 미확인 |

위 `/appdata`는 기존 운영 경로의 기록입니다. 새 업무 파일 데이터 경로는 `/data/<domain>` 계약을 따르며
이 문서 통합으로 기존 데이터·설정 경로를 변경하지 않습니다.

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
