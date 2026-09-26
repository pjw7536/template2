# 한 PC의 로컬 Kubernetes 개발 환경

`make dev`는 같은 컴퓨터의 kind에 Portal·Keycloak·Airflow·FTP·MinIO·mock·모니터링을 실행합니다.
control-plane과 worker는 Docker 컨테이너이며 별도 컴퓨터가 필요하지 않습니다.
PostgreSQL 16만 `tailwind-local-db` Compose project로 분리합니다. 기존 개발 DB는 변경하지 않습니다.

## 준비와 실행

Docker, Python 3 + PyYAML, kubectl, Helm 3.19.0 이상이 필요합니다.
kind는 `make k8s-tools`가 준비하며 `.tools/bin/helm`도 자동으로 PATH에 포함합니다.
Airflow·Monitoring chart는 기존 lock의 SHA-256으로 검증합니다. chart가 없으면 다음 명령으로 준비합니다.

```bash
python3 deploy/airflow/scripts/manage.py fetch-chart
python3 deploy/monitoring/scripts/manage.py fetch-chart
make k8s-check
make dev
make k8s-smoke
```

최초 이미지·패키지 다운로드에는 인터넷 연결이 필요합니다. 사내망은 사용하지 않습니다.
기반 이미지는 현재 Docker 캐시를 우선 반입합니다. MinIO 공개 registry에서 pull이 거부되면 준비된 이미지 archive를
`docker load`로 반입하거나 `LOCAL_MINIO_IMAGE`, `LOCAL_MINIO_CLIENT_IMAGE`에 접근 가능한 이미지 주소를 지정합니다.
Docker 메모리는 최소 10GiB, 전체 PC는 16GB 이상을 기준으로 합니다.
빌드·데이터용 디스크 여유 공간은 최소 15GiB가 필요합니다.

| 명령 | 동작 |
| --- | --- |
| `make dev`, `make k8s-up` | 전체 이미지 빌드·DB 연결·앱 배포·상태 확인 |
| `make k8s-rebuild APP=portal` | 선택 앱 갱신: portal, mock, airflow, keycloak, ftp, monitoring |
| `make k8s-check` | Kustomize·Helm·도구·설정 검사, 클러스터 변경 없음 |
| `make k8s-status`, `make k8s-health` | 상태·주소 표시, 준비 상태 확인 |
| `make k8s-smoke` | 로그인·챗/RAG·메일·MinIO·FTP 적재·Airflow·모니터링 통합 검사 |
| `make k8s-grafana`, `make k8s-prometheus` | localhost 3000·9090 port-forward |
| `make k8s-ui` | localhost 4466 Headlamp 조회 UI |
| `make down`, `make k8s-down` | kind와 새 DB 컨테이너 종료, 데이터 보존 |
| `make check-api`, `make makemigrations-check`, `make test-api` | 같은 이미지·새 DB를 사용하는 일회성 Compose api 검사 |

## 주소와 계정

`test-api`는 저장소의 표준 test env와 별도 Django 테스트 DB를 사용합니다.
`check-api`·`makemigrations-check`는 실제 합성된 로컬 Kubernetes env를 검사합니다.

- Portal: http://localhost:8080 — `90000001 / dummy-user-change-me` (내부 팀 계정)
- 다른 Portal 테스트 계정: `90000002` 메일 조회, `90000003` 전체 앱, `90000004` 전체 관리자, `90000005` 무권한. 비밀번호는 위와 같습니다.
- Keycloak: http://localhost:8180 — `local-keycloak-admin / local-keycloak-admin-change-me`
- Airflow: http://localhost:8080/airflow — Keycloak 로그인. `90000001` 관리자, `90000003` 일반 운영, 나머지 로그인 사용자는 기본 조회. 비밀번호는 Portal 테스트 계정과 동일합니다.
- FTP: localhost:6380, passive 8076–8079 — 사용자 `ftpuser`
- Grafana: `make k8s-grafana` 실행 중 http://localhost:3000 — 사용자 `admin`
- PostgreSQL: localhost:55432 — dashboard_keycloak/portal, airflow/airflow, keycloak/keycloak DB/계정

Portal은 EPID 인증용 `dashboard_keycloak` DB를 사용합니다. 로컬 기동은 최종 API env의
DB가 없을 때만 생성하며, 이전 `dashboard` DB는 보존합니다. 기존 업무 데이터는 새 DB에
자동 복사하지 않습니다. 테스트 데이터는 Portal seed 단계에서 준비합니다.

### Docker Desktop / WSL 재시작 후 복구

호스트의 `data/k8s-local`에는 파일이 있는데 worker의 `/data/local-runtime`이 비어 있거나,
PostgreSQL이 `10-apps.sh` bind mount 오류로 시작하지 못하면 저장소 루트에서 실행합니다.

```bash
docker restart tailwind-local-worker
docker compose --project-name tailwind-local-db --env-file local/shared/runtime/db.env \
  -f local/shared/compose/k8s-db.yml up -d --force-recreate --wait
make k8s-rebuild APP=portal
```

이 절차는 기존 DB 볼륨과 호스트 데이터를 유지하며 컨테이너 마운트를 다시 연결합니다.
Portal 갱신은 Secret의 폐기된 설정 키도 제거하여 현재 env와 일치시킵니다.
기존 Keycloak realm은 import로 덮어쓰지 않으므로, 이전 설치에서는 EPID 테스트 계정과
현재 Portal claim mapper를 별도로 반영해야 합니다.

생성된 DB·Airflow API·Grafana·FTP 비밀번호는 `local/shared/runtime/credentials.env`에 있습니다.
이 파일은 0600 권한으로 생성하고 Git에서 제외하며 재실행해도 덮어쓰지 않습니다.

## 로컬 설정과 파일 보존

공개 입력은 `local/shared/env/k8s.env.example`입니다. 필요한 항목만 `local/shared/env/k8s.env`에 작성합니다.
환경변수를 명시하면 같은 키의 파일 값보다 우선합니다. 상대 경로는 저장소 루트를 기준으로 해석합니다.

- `LOCAL_DB_PORT`, `LOCAL_FTP_PORT`, `LOCAL_FTP_PASSIVE_START`: 호스트 연결 포트.
- `LOCAL_RUNTIME_DATA_HOST_PATH`: 기본 `data/k8s-local`. API 작업 파일·MinIO·Airflow 로그·모니터링 데이터.
- `DATA_MOVEMENT_HOST_PATH`: 기본 `data/data_movement`. FTP와 API가 공유하는 읽기/쓰기 디렉터리.
- `L3_SPIDER_DATA_HOST_PATH`, `TTTM_SPIDER_DATA_HOST_PATH`, `PM_COMPARISON_DATA_HOST_PATH`: 기존 참고 데이터, 읽기 전용.

FTP 포트가 사용 중인 PC의 예:

```dotenv
LOCAL_FTP_PORT=16380
LOCAL_FTP_PASSIVE_START=18076
```

kind 포트·마운트 변경은 클러스터 재생성이 필요합니다. `make down` 후 `make dev`를 실행합니다.
DB volume과 호스트 파일, credentials.env는 보존됩니다. 정상 종료에서 volume 삭제나 seed reset은 실행하지 않습니다.
PostgreSQL은 `tailwind-local-db_postgres_data` volume을 사용합니다. runtime 디렉터리와 DB volume은 함께 백업합니다.
DB 컨테이너가 재생성되어 IP가 바뀌면 `make dev`가 Service/EndpointSlice를 갱신합니다.

## 설정 합성과 앱 경계

로컬 Kustomize 집계 진입점은 [shared/k8s](shared/k8s/kustomization.yaml)입니다.
`portal/k8s`를 직접 렌더하면 Portal과 MinIO만 포함됩니다. 전체 실행은 계속 `make dev`를 사용합니다.

| 소유 영역 | 배포 입력·도구 |
| --- | --- |
| `portal` | API·Web·MinIO·Ingress·migration·MinIO 스토리지 |
| `keycloak` | Keycloak Deployment·Service·realm ConfigMap |
| `headlamp` | Headlamp 조회 UI·RBAC·`scripts/headlamp-ui.sh` |
| `adfs_dummy` | mock 소스·이미지·Kubernetes Deployment·Service |
| `shared` | namespace·Traefik·외부 PostgreSQL Service·집계·전체 실행 도구 |
| `airflow`, `ftp`, `monitoring` | 각 앱의 기존 로컬 Helm values 또는 Kubernetes overlay |

각 앱의 Kubernetes 입력은 `local/<app>/k8s`에서 독립 렌더할 수 있습니다.
`make k8s-render-local`은 집계·앱별 원본·Portal migration·FTP를 함께 검사합니다.
앱별 렌더는 필요한 공통 기반·Secret·DB까지 기동하는 명령이 아닙니다.

API 입력 순서는 `local/portal/env/api.env` → `api-k8s.env` → 생성된 `runtime/api-overrides.env`입니다.
MinIO client credential만 추가해 API·migration·seed·collectstatic이 같은 Secret을 사용합니다.
`make k8s-env APP=portal PROFILE=local`도 같은 합성 함수를 사용합니다.
최초 migration 이후 seed는 기존 사용 데이터를 삭제하지 않고 실행합니다.

Portal은 기존 Kustomize base, FTP는 기존 DaemonSet, Airflow·Monitoring은 공통 Helm 배포 도구를 재사용합니다.
`local/airflow/helm/values.yaml`과 `local/monitoring/helm/values.yaml`만 개발 자원·보존 설정을 덮어씁니다.
Airflow는 새 DAG를 일시정지로 만들고 대표 테스트는 이전 활성 상태를 복원합니다.

인증은 Keycloak, RAG·LLM·메일·Jira는 `adfs_dummy`를 사용합니다.
POP3·사내 메신저 같은 실제 사내 연동은 기본 검증 범위에 포함하지 않습니다.
전체 업무 화면에 필요한 데이터는 기존 mock 생성 도구와 도메인별 데이터 안내를 따릅니다.
mock의 RAG·메일 샌드박스는 기존 구현처럼 메모리 저장소이며 mock Pod 재시작 시 기본 seed로 돌아갑니다.
업무 DB와 MinIO 파일·FTP 원본은 별도 영속 저장소에 유지됩니다.

## 서버 이전과 검사

공통 정의는 deploy, 소스는 apps, 로컬 차이는 local에 둡니다.
서버는 local 없이 `make server-check APP=all`로 검사할 수 있습니다.
서버 이전 시 registry·도메인/TLS·DB·스토리지·실제 외부계 설정을 지정합니다.
FTP와 API를 다른 노드에 두면 공유 저장소 또는 명시적인 노드 배치가 필요합니다.

```bash
make env-profile-key-check
make compose-check
make k8s-check
node --test apps/tooling/tests/*.test.cjs
python3 -m unittest discover -s apps/tooling/agent/tests -p test_local_k8s.py
```

통합 검사는 테스트 대화·메일·파일 적재 이력·DAG 실행을 생성합니다. 기존 DB나 파일을 초기화하지 않습니다.

### 역할 기반 Portal 표준 사용자

신규 로컬 realm의 `90000001` 계정은 `portal-members` 그룹에서 `portal-all-apps`를 상속합니다.
기존 realm은 import로 갱신되지 않습니다. 기존 환경은 Admin Console에서 `portal-members` 그룹을 생성하고,
Role mapping에 `portal` client의 `portal-all-apps`를 지정한 뒤 `90000001`을 가입시키고 재로그인합니다.
부서 정보만으로 앱에 접근할 수 없으며, 기존 SDWT 그룹은 유지합니다. DB나 realm을 초기화할 필요는 없습니다.

## Airflow Keycloak 로그인

`make k8s-rebuild APP=airflow`는 기존 realm을 보존하면서 전용 client를 등록하고 이미지를 갱신합니다.
새 환경의 `make dev`도 같은 등록 경로를 사용합니다. realm JSON의 재import에 의존하지 않습니다.
누락된 Airflow client secret만 `local/shared/runtime/credentials.env`에 추가하며 기존 DB·Fernet 키는 유지합니다.

로그인한 모든 사용자는 Viewer입니다. `airflow` client의 User·Admin 역할만 추가 권한으로 적용하고,
Portal 역할·조직·SDWT 그룹은 사용하지 않습니다. 로컬 테스트 계정 90000001에는 Admin,
90000003에는 User를 등록합니다. 서버 등록 도구는 사용자 역할을 자동 부여하지 않습니다.

```bash
make k8s-airflow-sso-check
```

이 검사는 실제 Keycloak 로그인·기본 조회·역할 회수 후 Viewer 복귀·기존 Basic API·Portal 조회를 확인합니다.
90000003의 역할을 잠시 제거한 뒤 원래대로 복원하며 DAG를 실행하지 않습니다.
Airflow 웹의 DB 비밀번호 로그인은 SSO로 대체되지만 기존 API 계정은 유지됩니다.
