# 05. 앱별 배포

[가이드 홈](README.md) · 이전: [배포 준비](04-prerequisites.md) · 다음: [검증](06-verification.md)

**CP1의 checkout 루트**에서 필요한 앱만 배포합니다. 04장의 context와 실제 입력이 준비되어 있어야 합니다.
`server-check`는 원본·입력 형식·렌더 검사이며 실제 기동 검증은 아닙니다. 각 검사가 성공한 뒤에만 적용합니다.

## 1. Keycloak·공용 Traefik

[Keycloak 상세 안내](../../../keycloak/README.md)의 env·인증서·Worker 디스크를 준비합니다.
APP VIP 최초 연결 또는 backend 변경 때는 **유지할 Worker IP 전체**를 입력합니다.
현재 기록은 [홈의 backend 표](README.md#현재-서버-상황)와 대조합니다.

```bash
read -r -p 'APP VIP의 전체 Worker backend IP 목록: ' VIP_BACKENDS
make server-check APP=keycloak PROFILE=prod
make keycloak-check KUBE_CONTEXT="$KUBE_CONTEXT" VIP_BACKENDS="$VIP_BACKENDS"
make keycloak-up KUBE_CONTEXT="$KUBE_CONTEXT" VIP_BACKENDS="$VIP_BACKENDS"
```

기존 backend를 유지하는 재배포는 `read`와 두 명령의 `VIP_BACKENDS` 인자를 생략할 수 있습니다.
외부 입력은 `KEYCLOAK_ENV`·`KEYCLOAK_CERTS`를 검사와 배포에 동일하게 전달합니다.
기존 Secret과 입력이 다르면 원본·실제 DB credential을 확인합니다. Secret·PVC 삭제로 우회하지 않습니다.

상세 안내의 사내 OIDC 연결·사용자 claim Job까지 완료한 뒤 PostgreSQL·Keycloak·Traefik 준비 상태와 HTTPS·사내 로그인을 확인합니다.
스택 배포만으로 OIDC·Portal client가 등록되지는 않습니다.

## 2. Airflow

[Airflow 상세 안내](../../../airflow/README.md)에 따라 env·chart·이미지·ODBC·DB/로그 디스크를 준비합니다.
APP VIP 경로는 공용 Traefik과 Airflow namespace의 [업무 도메인 TLS](../../ingress/VIP.md)가 필요합니다.

```bash
make server-check APP=airflow PROFILE=prod
make airflow-check KUBE_CONTEXT="$KUBE_CONTEXT"
make airflow-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

외부 env는 `AIRFLOW_ENV`, 기존 namespace에서 TLS를 최초 복사하면 `AIRFLOW_TLS_SOURCE`를 검사·배포 양쪽에 전달합니다.
Airflow 전용 명령은 Keycloak·Keycloak DB를 재배포하지 않습니다.

**완료 기준:** DB·Airflow 준비, `/airflow/health`의 DB·scheduler 정상, UI 로그인 성공.
Portal 연동은 토큰·API 주소와 시험 DAG 결과까지 확인합니다. 복원한 DB의 기존 활성 DAG도 확인한 뒤 업무 실행을 시작합니다.

## 3. Portal — 필요할 때

[Portal 입력](../../../portal/README.md)과 [운영 overlay 절차](../../../portal/k8s/overlays/prod/README.md)를 따릅니다.
현재 `make portal-up`은 없으며 상세 문서의 적용 명령을 사용합니다.

1. 외부 PostgreSQL·extension, API/Web 이미지, MinIO·업무 파일 저장소를 준비합니다.
2. 입력 검사와 Keycloak [client 등록](../../../portal/k8s/jobs/keycloak-client/README.md)을 완료합니다.
3. namespace·Secret·TLS·PVC를 준비합니다.
4. 배포할 API 이미지로 migration Job을 실행하고 완료를 확인합니다.
5. overlay 적용과 공용 Traefik의 Portal namespace 감시를 연결합니다.
6. API health·로그인/callback/logout·파일 업로드/다운로드를 확인합니다.

업무 파일을 보존해야 하는 `emptyDir` 경로는 실제 PVC 등으로 연결합니다.
배치 노드는 현재 Worker 자원·스토리지를 보고 정하며 과거 예정 서버를 자동 사용하지 않습니다.

## 4. 선택 운영 도구

각 앱의 `make server-check APP=앱 PROFILE=prod`와 상세 준비 절차를 먼저 수행합니다.

| 앱 | 적용 경로 | 완료 기준 |
| --- | --- | --- |
| [Monitoring](../../../monitoring/README.md) | `make monitoring-check` → `make monitoring-up KUBE_CONTEXT="$KUBE_CONTEXT"` | Grafana 로그인·노드 지표·Prometheus target |
| [Headlamp](../../../headlamp/README.md) | `make headlamp-check` → `make headlamp-up KUBE_CONTEXT="$KUBE_CONTEXT"` | Keycloak 그룹 계정으로 노드·Pod 조회 |
| [FTP](../../../ftp/README.md) | Worker 폴더·포트·Secret·라벨 준비 → 상세 apply | 노드 IP로 passive 접속·파일 송수신 |

Monitoring은 기본 port-forward, Headlamp HTTPS는 추가 설정, FTP는 노드 직접 접속입니다.
`make server-up`은 기존 Keycloak+Airflow 통합 운용용입니다. 공용 라우팅 연결 후 Keycloak 정적 YAML을 직접 적용하면 감시 범위·VIP 배치가 되돌아갈 수 있으므로 앱별 도구를 사용합니다.
