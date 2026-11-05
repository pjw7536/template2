# 운영 파일·데이터·백업·담당자

[사내 인프라 정보](README.md) · [공통 배포 문서](../README.md)

checkout·설정·인증서·kubeconfig·백업 보관 위치와 운영 책임의 관리 원본입니다.

기록 형식과 갱신 절차는 [공통 기록 규칙](README.md#기록-규칙)을 따릅니다.
**자료 대조일: 2026-11-05 / 담당자: 미확인.** 사용자 확인일과 실제 적용 여부는 각 항목의 근거를 따릅니다.

## 운영 파일과 데이터 위치

| 용도 | 위치·관리 방법 | 근거·확인 상태 |
| --- | --- | --- |
| 서버 Git checkout | `/appdata/etchax` | [선택 checkout](../../../01-SERVER_CHECKOUT.md)의 설치 경로. 현재 서버 경로 확인 필요 |
| CP1 외부 앱 설정 | `/appdata/etchax-config/<app>/` | [배포 안내](../../../README.md#소유권)의 기존 운영 기록. 앱 도구에 실제 외부 env 경로 명시 |
| 앱별 기본 env·Secret 입력 | `deploy/<app>/env/`와 앱별 별도 입력 | [환경설정](../configuration/environment.md). 실제 사용 파일은 앱별 절차에서 확인 |
| kubeconfig | 배포 계정의 `$HOME/.kube/config` 또는 지정한 `KUBECONFIG` | [CP1 운영](../operations/02-cp1.md). 실제 파일 위치·계정·권한 확인 필요 |
| 인증서·개인키·공용 CA | Git 밖의 서버 파일 | [인증서 관리](../../certs/README.md). 실제 보관 경로·담당자 확인 필요 |
| 앱 데이터·로그·ODBC | [앱별 배치·스토리지 표](services.md#앱별-배치와-스토리지-선언) | 노드별 PV·PVC·hostPath 선언과 실제 연결을 구분 |
| 백업·복구 파일 | 미확인 | 앱별 보관 위치·주기·보존 기간·복구 담당자 확인 필요 |

Worker의 앱 소유 호스트 경로는 `/appdata/<app 또는 domain>` 아래로 통일합니다.
컨테이너 내부 API 업무 파일은 `/data/<domain>` 계약을 유지합니다.
실행 설정은 앱별 manifest·env·Helm values에서 관리하고 이 문서의 운영 정보와 대조합니다.
비밀번호·토큰·개인키·kubeconfig 내용은 이 문서에 기록하지 않습니다.

## Worker 앱 데이터 경로와 이전

**설정 변경 요청일·저장소 대조일: 2026-11-05 / 근거: 사용자의 Worker 폴더 `/appdata` 통일 요청과 아래 배포 입력 / 담당자: 미확인.**
아래는 신규 설치의 기본 선언입니다. 실제 서버의 현재 경로·데이터 이전·적용 여부는 조회하지 않았으며,
운영 env의 사용자 지정 경로가 우선합니다. 기존 경로는 이전이 완료될 때까지 유지합니다.

| 대상 | 이전 저장소 기본값 | 새 호스트 기본값 | 설정 원본 |
| --- | --- | --- | --- |
| MinIO | `/data/minio` | `/appdata/minio` | `deploy/minio/env/prod.env`: `MINIO_DATA_HOST_PATH`, `scripts/manage.py` 기본값 |
| FTP 수신 파일 | `/data/data_movement` | `/appdata/data_movement` | `deploy/ftp/k8s/stack.yaml`: `volumes[].hostPath.path` |
| Airflow DB·로그·ODBC | `/srv/airflow/postgres`, `/srv/airflow/logs`, `/srv/airflow/odbc` | `/appdata/airflow/postgres`, `/appdata/airflow/logs`, `/appdata/airflow/odbc` | `deploy/airflow/env/k8s.env`: `POSTGRES_HOST_PATH`, `LOGS_HOST_PATH`, `ODBC_HOST_PATH` |
| Monitoring | `/srv/monitoring` 아래 서비스별 폴더 | `/appdata/monitoring` 아래 `prometheus`, `alertmanager`, `grafana` | `deploy/monitoring/env/k8s.env`: `DATA_HOST_PATH` |
| Keycloak DB | `/appdata/keycloak-postgres` | 동일 | `deploy/keycloak/k8s/server/stack.yaml`: `spec.local.path` |

Portal의 운영 업무 파일은 아직 `emptyDir`이며 영구 저장소로 전환되지 않았습니다.
운영 PVC를 준비할 때 노드의 업무 파일 경로를 위 기준에 맞추고 API의 `/data/<domain>`에 연결합니다.
FTP와 같은 파일을 읽는 앱은 같은 노드의 같은 데이터 또는 명시적으로 준비한 공유 저장소에 연결해야 합니다.
동적 StorageClass의 실제 저장 위치, kubelet·container runtime, node-exporter가 읽는 시스템 볼륨,
외부 PC의 kind 호스트 매핑은 이 변경에 포함하지 않습니다.

### 방향과 디스크 확인

호스트의 앱 데이터·로그·설정 파일을 한 루트에 모으면 디스크 사용량·권한·백업 대상을 관리하기 쉽습니다.
`/appdata`라는 이름 자체에 Kubernetes의 특별한 동작은 없으며, local PV·hostPath의 노드 종속성과 장애 복구 요구는 그대로입니다.
앱마다 필요한 UID/GID와 권한은 유지하고 `/appdata` 전체에 재귀 `chown`을 적용하지 않습니다.

각 Worker에서 `/appdata`가 의도한 데이터 파일시스템에 있는지 확인합니다. 전용 디스크를 사용할 계획이면
부팅 시 마운트가 준비된 뒤 Pod가 시작되게 노드에서 구성합니다. 마운트 누락 상태에서 자동 폴더 생성에 의존하면
OS 디스크에 기록될 수 있습니다. 다음 명령은 조회만 수행합니다.

```bash
findmnt -T /appdata
df -hT /appdata
```

`/appdata`가 아직 없다면 부모 파일시스템·마운트 계획을 먼저 확인합니다.
local PV의 용량 선언은 디스크 할당이나 사용량 제한이 아니므로 실제 여유 공간도 별도로 확인합니다.

### 기존 설치 전환 순서

1. 대상 context·Worker·외부 env, Pod의 volumeMount·hostPath, PVC와 PV의 `spec.local.path`·nodeAffinity·claimRef·reclaim policy를 기록합니다. 원본 manifest와 앱 설정을 보관하고 실제 데이터 디스크·백업 복구 가능 여부를 확인합니다.
2. 이전 전까지 외부 env에 현재 경로를 명시합니다. MinIO의 경로 키가 없는 env도 새 기본값을 사용하므로 기존 `/data/minio` 설치에는 `MINIO_DATA_HOST_PATH=/data/minio`가 필요합니다. Airflow·Monitoring도 현재 경로를 유지합니다. FTP를 먼저 재배포해야 한다면 외부 overlay의 hostPath를 현재 경로로 유지합니다.
3. 해당 앱과 쓰기 클라이언트·작업을 중지하고 중지가 완료됐는지 확인합니다. FTP는 대상 노드의 FTP Pod와 파일 소비 작업을 함께 중지합니다. DB와 MinIO는 앱별 백업·복구 절차를 우선하며 실행 중인 데이터 폴더를 그대로 복사하지 않습니다.
4. 의도한 디스크 아래 새 폴더를 준비하고, 정지한 데이터 또는 검증한 백업을 복사·복원합니다. 숨김 파일·소유권·권한·필요한 ACL을 보존하고 원본은 삭제하지 않습니다. Airflow ODBC도 읽기 권한을 보존합니다. 노드별 FTP 파일은 노드별로 옮깁니다.
5. FTP는 새 hostPath가 준비된 뒤 원본 또는 운영 overlay로 전환합니다. 컨테이너 경로 `/data/data_movement`와 로그인 후 `data_movement/`는 유지합니다. 같은 파일을 소비하는 앱의 PV·hostPath도 새 호스트 경로에 맞춥니다.
6. 정적 local PV는 `spec.local.path`를 일반 `apply`로 수정할 수 없습니다. MinIO·Airflow·Monitoring은 별도 PV/PVC 전환을 준비합니다. 기존 PV의 `Retain`을 확인하고 새 경로의 PV와 앱이 참조할 PVC를 맞춘 뒤 전환합니다. 도구가 고정하는 PV/PVC 이름과 Helm release의 claim 이름도 함께 대조합니다. 기존 이름을 재사용해야 한다면 서비스 정지·백업 상태에서 저장소 관리자와 재생성·재결합 절차를 확정합니다. PVC/namespace 일괄 삭제나 PV 강제 교체로 전환하지 않습니다.
7. env·overlay를 새 경로로 맞춘 뒤 관련 `server-check`와 렌더 검사를 수행합니다. 재기동 후 Pod 노드·실제 마운트·PVC Bound, 기존 DB·파일·계정·대시보드·로그를 확인하고 업로드·다운로드·업무 동작을 검사한 후 쓰기를 재개합니다.
8. 검증이 실패하면 쓰기를 중지한 상태에서 보관한 env·manifest·원본 PV/PVC 연결로 복귀합니다. 새 경로에서 쓰기를 재개한 뒤에는 변경분 정합성을 확인한 후 롤백합니다. 기존 데이터 정리는 정상 운영·복구 검증과 보존 기간 확인 후 별도로 수행합니다.

앱별 절차: [MinIO 저장소](../../../minio/README.md#저장소-자동-준비), [Airflow 백업·이전](../../../airflow/05_OPERATIONS.md),
[Monitoring 운영](../../../monitoring/README.md#갱신운영), [FTP 운영](../../../ftp/02_OPERATIONS.md).
실제 적용 후에는 [서비스 배치·스토리지](services.md#앱별-배치와-스토리지-선언)에 대상 노드·현재 경로·검증일·담당자를 기록합니다.

## 운영 책임·백업·인증서

| 대상 | 기록할 정보 | 현재 상태 |
| --- | --- | --- |
| 서비스별 운영 책임 | 담당자·장애 연락 경로·접근 권한 신청 절차 | 미확인 |
| 데이터 백업 | 대상·보관 위치·주기·보존 기간·복구 담당자·마지막 복구 검증일 | 미확인 |
| 인증서·공용 CA | 보관 위치·만료일·갱신 담당자·적용 Secret 이름·마지막 갱신 확인일 | 상세 절차는 [인증서 관리](../../certs/README.md), 실제 운영값은 추가 확인 필요 |

## 변경 연계와 조회

데이터를 옮기면 [서비스의 배치·스토리지](services.md#앱별-배치와-스토리지-선언), 대상 Worker는 [서버 목록](servers.md)을 함께 확인합니다.
노드별 local PV·hostPath는 해당 노드의 데이터이며 다른 Worker로 이동할 때 별도 이전·복구가 필요합니다.
실행 절차는 [CP1 운영](../operations/02-cp1.md), [서버 기동](../operations/01-server-start.md), [환경설정](../configuration/environment.md)을 따릅니다.

## 실행 설정의 원본

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
