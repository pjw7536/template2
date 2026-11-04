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

위 `/appdata`는 기존 운영 경로의 기록입니다. 새 업무 파일 데이터는 `/data/<domain>` 계약을 따릅니다.
실행 설정은 앱별 manifest·env·Helm values에서 관리하고 이 문서의 운영 정보와 대조합니다.
비밀번호·토큰·개인키·kubeconfig 내용은 이 문서에 기록하지 않습니다.

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
