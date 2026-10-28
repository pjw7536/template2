# 05. 앱별 배포

[가이드 홈](README.md) · 이전: [배포 준비](04-prerequisites.md) · 다음: [검증](06-verification.md)

04장에서 context와 실제 입력을 준비한 뒤 **CP1의 checkout 루트**에서 실행합니다.
필요한 앱만 골라 배포하고, 각 검사가 성공한 뒤 적용 단계로 넘어갑니다.
첫 단계는 `platform`으로 Portal 외 서비스를 운영하며, Portal은 이후 `all`로 선택 범위를 확장해 추가합니다.

`server-check`는 배포 정의·입력 형식·렌더 결과를 확인합니다.
실제 앱이 기동하고 접속되는지는 배포 후 따로 확인해야 합니다.

## 1. 공용 Traefik

기존 Ready 클러스터에서 앱보다 먼저 공용 Ingress를 준비합니다.
이 명령은 Portal·Keycloak env나 앱 소스 없이 공용 리소스만 검사·적용합니다.

```bash
make ingress-check KUBE_CONTEXT="$KUBE_CONTEXT"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

현재 controller가 있으면 기존 namespace 감시와 VIP 배치를 보존합니다.
APP VIP의 Worker backend는 [VIP 안내](../../ingress/VIP.md)에 따라 확인합니다.
앱·DB·Secret은 이 단계에서 배포하지 않습니다.

## 2. Keycloak

[Keycloak 최초 설치 안내](../../../keycloak/README.md)에서 서버 준비·배포 → 자체 설정·사내 로그인 확인까지 완료합니다.
입력 파일·context 선택·검사·적용 명령은 Keycloak 문서에서 관리합니다.
APP VIP의 Worker backend와 공용 경로는 [VIP 안내](../../ingress/VIP.md)를 함께 확인합니다.
Portal·Headlamp client 연결은 Keycloak 준비를 마친 뒤 수행합니다.

## 3. Airflow

[Airflow 상세 안내](../../../airflow/README.md)에 따라 env·chart·이미지·ODBC·DB/로그 디스크를 준비합니다.
현재 설치는 기존 DB를 이전하지 않고 새 DB로 시작합니다. Keycloak 전용 Worker를 제외하고
자원·저장소를 확인한 Worker를 `NODE_NAME`에 지정합니다.
APP VIP 경로는 공용 Traefik과 Airflow namespace의 [업무 도메인 TLS](../../ingress/VIP.md)가 필요합니다.

```bash
make server-check APP=airflow PROFILE=prod
make airflow-check KUBE_CONTEXT="$KUBE_CONTEXT"
make airflow-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

기본 위치가 아닌 env는 `AIRFLOW_ENV`로 지정합니다.
기존 namespace의 TLS 인증서를 처음 복사할 때는 `AIRFLOW_TLS_SOURCE`도 지정합니다.
두 값은 검사 명령과 배포 명령에 동일하게 전달합니다.
Airflow 전용 명령은 Keycloak·Keycloak DB를 재배포하지 않습니다.

**완료 기준:** DB·Airflow 준비, `/airflow/health`의 DB·scheduler 정상, UI 로그인 성공.
Portal 연동은 토큰·API 주소와 시험 DAG 결과까지 확인합니다. 필요한 DAG만 검증 후 활성화합니다.

## 4. 운영 도구

각 앱의 `make server-check APP=앱 PROFILE=prod`와 상세 준비 절차를 먼저 수행합니다.

| 앱 | 적용 경로 | 완료 기준 |
| --- | --- | --- |
| [Monitoring](../../../monitoring/README.md) | `make monitoring-check` → `make monitoring-up KUBE_CONTEXT="$KUBE_CONTEXT"` | Grafana 로그인·노드 지표·Prometheus target |
| [Headlamp](../../../headlamp/README.md) | 서버·TLS/CA → 전용 client·그룹·Secret → 모든 API server OIDC 설정 → `headlamp-check`·`headlamp-up` | 관리자 로그인·자원 접근 성공, 별도 권한 없는 비관리자 접근 거부 |
| [FTP](../../../ftp/README.md) | Worker 폴더·포트·계정 파일 준비 → `make ftp-check` → `make ftp-up` | 노드 IP로 passive 접속·파일 송수신 |

접속 방식은 앱마다 다릅니다. Monitoring은 기본적으로 port-forward, FTP는 노드 IP로 직접 접속합니다.
Headlamp는 위 준비 단계를 마친 뒤 배포합니다. `headlamp-check/up` 두 명령만으로 인증 준비가 완료되지는 않습니다.
FTP 명령에는 상세 문서대로 `KUBE_CONTEXT`, `FTP_NODES`, `FTP_CREDENTIAL_FILE`을 전달합니다.

## 5. Portal — 나중에 추가

기반 앱을 유지한 채 Portal 배포 파일을 추가합니다.

```bash
bash deploy/shared/scripts/checkout-server.sh all
make server-check APP=portal PROFILE=prod
```

선택은 기존 범위를 교체하므로 `portal`만 선택하지 않습니다.

[Portal 입력](../../../portal/README.md)과 [운영 overlay 절차](../../../portal/k8s/overlays/prod/README.md)를 따릅니다.
현재 `make portal-up`은 없으며 상세 문서의 적용 명령을 사용합니다.

1. 외부 PostgreSQL·extension, API/Web 이미지, MinIO·업무 파일 저장소를 준비합니다.
2. 입력 검사와 Keycloak [client 등록](../../../portal/k8s/jobs/keycloak-client/README.md)을 완료합니다.
3. namespace·Secret·TLS·PVC를 준비합니다. `make k8s-env`에는 `KUBE_CONTEXT="$KUBE_CONTEXT"`를 전달합니다.
4. 배포할 API 이미지로 migration Job을 실행하고 완료를 확인합니다.
5. overlay로 `portal-traefik` 권한을 적용한 뒤 `make ingress-connect APP=portal KUBE_CONTEXT="$KUBE_CONTEXT"`로 공용 Traefik의 감시를 연결합니다.
6. API health·로그인/callback/logout·파일 업로드/다운로드를 확인합니다.

업무 파일을 보존해야 하는 `emptyDir` 경로는 실제 PVC 등으로 연결합니다.
배치 노드는 현재 Worker 자원·스토리지를 보고 정하며 과거 예정 서버를 자동 사용하지 않습니다.

`make server-up`은 기존 Keycloak+Airflow 통합 운용에 사용하는 명령입니다.
공용 라우팅을 연결한 뒤에는 앱별 배포 도구를 사용합니다.
Keycloak 정적 YAML을 직접 적용하면 namespace 감시 범위와 VIP 배치가 기본값으로 돌아갈 수 있습니다.
