# 서비스·앱 배치·업무 연동

[사내 인프라 정보](README.md) · [공통 배포 문서](../README.md)

서비스 URL·namespace·배치 입력·스토리지 연결과 사내 업무 연동 주소의 관리 원본입니다.

기록 형식과 갱신 절차는 [공통 기록 규칙](README.md#기록-규칙)을 따릅니다.
담당자는 미확인입니다. 설정 원본과 운영 적용 여부는 아래 항목을 따릅니다.

## 서비스 접속 주소

아래는 배포 선언 또는 앱 운영 안내의 주소입니다. 실제 DNS 응답·인증서·접속 성공은 별도 확인이 필요합니다.
클러스터 내부 주소는 Pod 간 통신용이며 운영 PC에서의 직접 접속 주소가 아닙니다.

| 서비스·용도 | 주소 | 근거 |
| --- | --- | --- |
| Portal·업무 서비스 기본 도메인 | `https://etch.samsungds.net/` | Portal prod Ingress |
| Keycloak | `https://etch-sso.samsungds.net/` | Keycloak Ingress |
| 업무 realm OIDC issuer | `https://etch-sso.samsungds.net/realms/etch` | Airflow·Headlamp OIDC env |
| 사내 AD FS OIDC discovery | `https://stsds.secsso.net/adfs/.well-known/openid-configuration` | `deploy/keycloak/env/prod.env`의 `CORP_OIDC_DISCOVERY_URL` |
| Airflow | `https://etch.samsungds.net/airflow` | Airflow `AIRFLOW_WEBSERVER_BASE_URL` |
| MinIO 콘솔 | `https://etch.samsungds.net/minio-console/` | MinIO env·운영 안내 |
| MinIO 파일 공개 경로 | `https://etch.samsungds.net/minio/` | MinIO 운영 안내 |
| Grafana | `https://etch.samsungds.net/grafana/` | Monitoring 운영 안내 |
| Prometheus 수집 대상 | `https://etch.samsungds.net/prometheus/targets` | Monitoring 운영 안내 |
| Alertmanager | `https://etch.samsungds.net/alertmanager/` | Monitoring 운영 안내 |
| Headlamp | `https://etch.samsungds.net/headlamp/` | Headlamp 운영 안내 |
| MinIO S3·클러스터 내부 | `http://minio.minio.svc.cluster.local:9000` | MinIO 운영 안내 |
| Portal API·클러스터 내부 | `http://api.tailwind-internal.svc.cluster.local:8000` | Airflow `AIRFLOW_API_BASE_URL` |
| FTP | 선택한 FTP 노드 InternalIP의 TCP 6380 | [노드별 수신 운영 방향](#ftp-노드별-파일-수신). 실제 배포 대상·전송 성공은 미확인 |
| 외부 PostgreSQL 등 추가 접속점 | 미확인 | Portal 운영 DB 주소 추가 확인 필요 |

근거는 [Portal overlay](../../../portal/k8s/overlays/prod/README.md), [Keycloak](../../../keycloak/README.md),
[Airflow](../../../airflow/README.md), [MinIO](../../../minio/README.md), [Monitoring](../../../monitoring/README.md), [Headlamp](../../../headlamp/README.md)의 원본·안내입니다.

### Portal 테스트·운영 접속 구분

사용자가 확인한 Portal 구성은 서로 다른 서버의 Docker 기반 테스트·운영 환경입니다.
기존 전달 방식은 `stg.plane`에서 확인한 뒤 `plane` 서버에서 재빌드하여 운영에 반영하는 방식입니다.
전환 목표는 테스트·운영 모두 현재 준비 중인 Kubernetes 클러스터에서 실행하고
`stg.plane`·`plane` 주소를 유지하는 것입니다. 전환 범위·주소 유지는 사용자 확인이며,
Argo 없이 검증한 이미지를 운영으로 승격하는 도구의 구현·운영 적용은 미확인입니다.
담당자는 미확인입니다.

| 환경·대상 | 현재 값·용도 | 확인 상태·설정 근거 | 남은 확인 |
| --- | --- | --- | --- |
| Portal 테스트 | `stg.plane`에서 테스트. 별도 Docker 서버에서 현재 준비 중인 Kubernetes 클러스터로 전환 예정, 주소 유지 | 사용자 확인. `apps/portal/web/vite.config.mjs`에는 `stg.plane.samsungds.net`의 Vite 개발 서버 host·HMR 설정이 있고 `local/portal/env/`에도 해당 도메인 참조가 있음 | [서버 원본](servers.md#portal-docker-환경)·전체 URL·DNS/TLS 전환·DB/스토리지 분리 여부, 전환할 context/namespace·노드·이미지와 실제 적용 |
| Portal 운영 | `plane`에서 운영. Docker 서버 재빌드 방식에서 같은 Kubernetes 클러스터로 전환 예정, 주소 유지 | 사용자 확인. 현재 `deploy/portal/k8s/overlays/prod/ingress.yaml`은 위 서비스 표의 `etch.samsungds.net`을 선언 | [서버 원본](servers.md#portal-docker-환경)·전체 URL, `plane`과 `etch`의 관계·DNS/TLS 전환·배포 원본, 전환할 context/namespace·노드와 실제 적용 |

`stg.plane`의 개발 서버 설정만으로 운영과 같은 빌드 이미지가 배포되어 있다고 판단하지 않습니다.
테스트·운영의 DNS 연결 대상·VIP·TLS는 [네트워크 원본](network.md)과 대조하고,
접속 관계가 확정되기 전에는 기존 Ingress·env의 도메인을 자동 교체하지 않습니다.

### 사내 업무 연동 주소

아래는 `deploy/portal/env/prod/api.env`·`web.env`의 선언입니다. 대상 주소는 보존하되 접속 성공·계정 권한은 별도 확인합니다.

| 연동·용도 | 주소 | 설정 키 |
| --- | --- | --- |
| RAG 검색 | `http://apigw.samsungds.net:8000/ds_llm_rag/2/dsllmrag/elastic/v2/retrieve-rrf` | `RAG_SEARCH_URL` |
| RAG 문서 등록 | `http://apigw.samsungds.net:8000/ds_llm_rag/2/dsllmrag/elastic/v2/insert-doc` | `RAG_INSERT_URL` |
| RAG 문서 삭제 | `http://apigw.samsungds.net:8000/ds_llm_rag/2/dsllmrag/elastic/v2/delete-doc` | `RAG_DELETE_URL` |
| RAG 인덱스 정보 | `http://apigw.samsungds.net:8000/ds_llm_rag/2/dsllmrag/elastic/v2/index-info` | `RAG_INDEX_INFO_URL` |
| Knox Messenger | `https://openapi.samsungds.net/messenger/` | `KNOX_MESSENGER_API_BASE_URL` |
| SOP Defectmap | `http://10.172.114.185:30912/defectmap` | `DRONE_SOP_DEFECTMAP_URL` |
| CTTTM | `https://ctttm.eqms.samsungds.net:7443/tttm/autoReport/qckLnk/mainInfo.do?wono=` | `DRONE_CTTTM_BASE_URL`. 뒤에 작업 번호를 연결하는 기본 주소 |
| RACB 보고서 | `https://racb.eqms.samsungds.net:7443/racb/rpt/ReportPop.do` | `RACB_REPORT_BASE_URL` |
| Defect Spider | `http://10.173.129.168:32600` | `VITE_DEFECT_SPIDER_URL` |

## 앱별 배치와 스토리지 선언

이 Kubernetes 구성에서 사용자가 확인한 운영 앱은 Keycloak·MinIO이며 MinIO에는 데이터가 없습니다.
Portal의 [테스트·운영 환경](#portal-테스트운영-접속-구분)은 별도 Docker 서버에서 이 클러스터로
함께 전환할 예정입니다. namespace·노드·스토리지 선택과 실제 전환 적용은 미확인입니다.
MinIO는 데이터 이관 없이 `/appdata/minio` 저장소로 재생성할 예정입니다.
실제 namespace·PV/PVC 이름·현재 호스트 경로와 재생성 완료 여부는 서버 조회·적용 후 확인해야 합니다.
나머지 앱의 아래 값은 설치 완료 기록이 아닌 배포 입력입니다.

아래는 저장소에 선언된 값입니다. **실제 Pod 배치·PV 연결·백업 상태는 서버 조회로 별도 확인이 필요합니다.**
외부 env를 지정하면 저장소 기본값과 다를 수 있습니다. 선택 checkout에 없는 앱은 해당 앱을 선택한 뒤 원본을 확인합니다.
Worker 앱 호스트 경로의 기본값은 `/appdata` 아래입니다.
기존 설치의 경로가 다르면 [데이터 이전](operations.md#worker-앱-데이터-경로와-이전)을 따릅니다.
노드 배치는 각 앱의 `nodeSelector`·affinity·env, 저장공간은 PV·PVC·Helm values와 대조합니다.

| 앱·공통 구성 | namespace | 배치 입력 | 스토리지·설정 원본 |
| --- | --- | --- | --- |
| 공용 Traefik | `etch-sso` | 기본 `khplane01w09`. VIP 확장 시 기존 배치를 보존하고 backend별 배치 계산 | `deploy/shared/ingress/stack.yaml`, [Ingress 운영](../../ingress/README.md) |
| Keycloak·전용 PostgreSQL | `etch-sso` | `khplane01w09` | 정적 local PV 50Gi, `/appdata/keycloak-postgres`. `deploy/keycloak/k8s/server/stack.yaml`, [Keycloak 안내](../../../keycloak/README.md) |
| Portal | `tailwind-internal` | 운영 Worker·이미지 미확정 | 외부 PostgreSQL, 공용 MinIO 사용. 업무 파일 기본 `emptyDir`는 운영 PVC로 교체 필요. [prod overlay](../../../portal/k8s/overlays/prod/README.md) |
| MinIO | `minio` | `NODE_NAME=khplanew01` | PVC 10Gi, 기본 정적 모드 `/appdata/minio`. `deploy/minio/env/prod.env`, [MinIO 안내](../../../minio/README.md) |
| Airflow·전용 PostgreSQL | `airflow` | `khinfow01` 배포 대상, 사용자 확인. [클러스터 Worker 추가](servers.md#서버-목록)는 사용자 확인. Ready·배포 적용은 미확인 | DB `/appdata/airflow/postgres` 20Gi, 로그 `/appdata/airflow/logs` 20Gi, ODBC `/appdata/airflow/odbc`. `deploy/airflow/env/k8s.env`, [Airflow 안내](../../../airflow/README.md) |
| Monitoring | `monitoring` | Airflow와 같은 `khinfow01` 배포 대상, 사용자 확인. [클러스터 Worker 추가](servers.md#서버-목록)는 사용자 확인. Ready·전체 배포 상태는 추가 확인 필요 | `DATA_HOST_PATH=/appdata/monitoring` 아래 local PV. 저장 폴더 준비 완료는 사용자 확인. Pod·PVC·웹 접속·지표 수집은 추가 확인 필요. `deploy/monitoring/env/k8s.env`, [폴더 준비 계약](operations.md#worker-앱-데이터-경로와-이전), [Monitoring 안내](../../../monitoring/README.md) |
| Headlamp | `headlamp` | 실제 배치 노드 미확인 | Helm values·`deploy/headlamp/env/k8s.env`로 관리. [Headlamp 안내](../../../headlamp/README.md) |
| FTP | `etch-ftp` | `etch.io/ftp-enabled=true`인 Linux 노드별 DaemonSet | hostPath `/appdata/data_movement`, 없으면 `DirectoryOrCreate`로 생성. 노드 간 자동 복제 없음. `deploy/ftp/k8s/stack.yaml`, [FTP 안내](../../../ftp/README.md) |

공용 진입점의 확장과 앱·DB의 복제 여부를 구분합니다. 특히 local PV·hostPath는 해당 노드의 데이터이며
다른 Worker로 옮길 때 별도 이전·복구가 필요합니다. 자원 용량·replica와 실제 여유는 앱 원본·클러스터에서 확인합니다.

## FTP 노드별 파일 수신

아래는 `deploy/ftp/k8s/stack.yaml`과 `deploy/ftp/env/prod.env`의 배포 설정입니다.
실제 서버 적용·접속 성공·담당자는 미확인입니다.

| 구분 | 운영 방향·설정 | 확인 상태·남은 확인 |
| --- | --- | --- |
| 접속·배치 | FTP가 필요한 Linux 노드의 IP로 직접 접속. `etch.io/ftp-enabled=true` 라벨에 따라 노드당 DaemonSet Pod 1개 | `FTP_ALLOW_CONTROL_PLANE` 기본값·생략값은 true로 Worker와 명시한 control plane의 역할 NoSchedule 허용. false를 명시하면 control plane 선택 거부. 기타 차단 taint는 유지. 실제 대상 노드·기동 여부 미확인 |
| 데이터 | 접속한 노드의 `/appdata/data_movement`에 저장. `DirectoryOrCreate`로 없는 폴더를 생성하고 FTP 시작 시 최상위 소유자를 설정. 로그인 후 경로는 `data_movement/` | 실제 서버 적용·폴더 자동 생성 여부 미확인. 노드별 디스크·기존 파일 권한·소비 앱의 읽기 위치 확인 필요. 자동 복제 없음 |
| 이미지·계정 | `deploy/ftp/env/prod.env`의 [FTP 미러 주소](repositories.md#이미지패키지별-사용-주소)·선택 pull Secret을 `ftp-up`이 적용. 추가 패치는 수동 overlay 사용. `etch-ftp/ftp-credentials` 공용 계정 사용 | 미러의 digest 제공·실제 pull·CA·인증·pull Secret 필요 여부 미확인 |
| 완료 판정 | 각 대상 노드에서 로그인·목록·업로드·다운로드와 호스트 파일 확인 | 전송 성공 여부 미확인. 대상 노드·접속 주소·검증 결과·담당자 확인 필요 |

노드명·IP는 [서버 목록](servers.md), 포트·방화벽은 [FTP 네트워크](network.md#ftp-직접-접속)를 따릅니다.
실행 순서는 [Worker별 준비](../../../ftp/01_SERVER_SETUP.md) → [운영 env 확인과 CP1 배포](../../../ftp/01_SERVER_SETUP.md#5-검사-후-배포) → [전송 확인](../../../ftp/02_OPERATIONS.md)입니다.
별도 overlay 운영은 [수동 사내 배포](../../../ftp/03_KUBERNETES.md#사내-이미지로-각-worker에-배포)를 따릅니다.
새 확인을 받으면 위 현재 값을 갱신하고 실제 배포 대상·주소·결과를 기록합니다.

## 추가 확인·변경 연계

서비스별 실제 설치 여부·Pod 배치·접속 상태·담당자는 새 확인을 받을 때 해당 표에 반영합니다.
외부 PostgreSQL 접속점과 FTP 실제 배포 대상은 미확인입니다. 앱의 실행 입력은 위 근거 파일에서 관리합니다.
도메인·VIP는 [네트워크](network.md), 노드·버전은 [서버](servers.md), 데이터·백업 보관 위치는 [운영 위치](operations.md)를 함께 갱신합니다.
