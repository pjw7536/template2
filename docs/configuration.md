# 환경 설정

외부 PC 환경 변수는 `local/<app>/env/`, 사내·CI 입력은 `deploy/<app>/env/`에서 관리합니다. 파일 위치와 검사·적용 명령은
[앱별 환경설정 안내](../deploy/shared/docs/configuration/environment.md)를 먼저 참고합니다. 외부 시스템 URL, token,
credential은 코드에 하드코딩하지 않고 env로 주입합니다.
Portal의 환경 선택과 사내 배포 입력 순서는 [Portal 환경설정](../deploy/portal/README.md)에 정리되어 있습니다.

## 파일별 역할

| 파일 | 사용처 | 역할 |
| --- | --- | --- |
| `local/portal/env/<service>.env` | 로컬 | API/Web/MinIO 설정, credential과 dummy 외부계 연결 |
| `deploy/portal/env/test/api.env` | API test | 임시 PostgreSQL, 테스트 credential과 외부 호출 차단 설정 |
| `local/portal/env/api-k8s.env` | 로컬 Kubernetes | local API 입력에 한 번만 적용하는 명시적 실행 차이 |
| `deploy/portal/env/prod/api.env` | 사내 Kubernetes | Portal API 및 Keycloak client 등록 입력, Git 제외 |
| `deploy/portal/env/prod/web.env`, `minio.env` | 사내 Kubernetes | 브라우저 공개 설정과 파일 저장소 계정, 각각의 `.example`에서 준비 |
| `deploy/keycloak/env/prod.env` | 사내 Keycloak | 서버 기동 및 선택적인 사내 OIDC 설정, Git 제외 |
| `deploy/airflow/env/k8s.env`, `local/shared/scripts/k8s_config.py` | Airflow | 앱별 실행 환경 설정 |
| `deploy/monitoring/env/k8s.env` | Monitoring | Kubernetes 노드·local PV·이미지 미러·Grafana Secret 참조 |

## 환경별 dependency source 정책

이 repo의 실행 환경은 dependency source 기준으로 아래처럼 나눕니다.

| 환경 | 실행 명령 | 용도 | Docker image | package manager |
| --- | --- | --- | --- | --- |
| `dev` | `make dev` | 로컬 개발 전용 | public registry | public source |
| `prod` | [운영 배포 안내](../deploy/portal/k8s/overlays/prod/README.md) | 사내 Kubernetes | internal mirror | 이미지 빌드 시 설정 |

`dev`는 로컬 PC에서만 사용하는 개발 환경입니다.
내부 mirror 주소인 `repository.samsungds.net`에 의존하지 않습니다.
`prod`는 외부 public 저장소를 직접 사용하지 않고 내부 mirror를 사용합니다.

## 환경·이미지 관리 원칙

사내 서버와 로컬 앱은 Kubernetes를 사용합니다. 공통 정의는 `deploy`, 로컬 차이는 `local`에서 관리합니다.
Compose는 로컬 PostgreSQL·일회성 API 검사·독립 CI에만 사용합니다.

- 실제 credential은 Git 제외 env에 두고 Kubernetes Secret으로 전달합니다. 공개 예시에 비밀값을 넣지 않습니다.
- 로컬 API는 기본 env → `api-k8s.env` → runtime override → MinIO client credential 순서로 합성합니다.
- 사내 Portal은 `deploy/portal/env/prod` 입력만 사용합니다. `make prod-profile-env-check`로 필수 입력을 검사합니다.
- Airflow의 DB·관리자·Portal 연결은 `deploy/airflow/env/k8s.env`에 둡니다. API의 Airflow 사용자·비밀번호·trigger token을 함께 맞춥니다.
- 로컬 Airflow와 API의 공용 credential은 실행 도구가 생성·재사용합니다. 로컬 개발은 사내망에 의존하지 않습니다.
- Web 공개 설정에는 secret을 넣지 않습니다. 정적 Web은 시작 시 `/runtime-env.js`를 생성합니다.
- 이미지 registry와 package mirror는 이미지 빌드·배포 입력으로 지정합니다. 전체 목록은 [mirror 참고](integrations/proxy-mirrors.md)를 봅니다.
- Airflow 사내 의존성 이미지 빌드 입력은 `deploy/airflow/env/build.env`입니다. 승인된 버전 고정 ODBC artifact는 `BIGDATAQUERY_ODBC_DEB_URL`로 전달하며 로컬 개발 빌드에는 사용하지 않습니다.
- Airflow ODBC 설정은 서버 `ODBC_HOST_PATH`를 `/usr/local/odbc`에 read-only로 연결하거나 `ODBC_SECRET_NAME`을 사용합니다. 실제 설정을 이미지나 Git에 넣지 않습니다.
- Kubernetes Airflow는 기존 실행 용량과 `default_pool=-1`을 유지합니다. 로컬 자원 제한은 별도 Helm values로 지정합니다.
- `make env-profile-key-check`는 공개 입력·예시의 존재와 중복 키를 확인하며 실제 운영 env 없이도 동작합니다.
- `make compose-check`는 가짜 입력으로 남은 세 Compose를 검사합니다. 서버 원본은 `make server-check APP=<앱>`으로 검사합니다.

## 주요 설정 그룹

| 그룹 | 대표 변수 | 설명 |
| --- | --- | --- |
| `DJANGO_*` / Django runtime | `ENVIRONMENT`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_TIME_ZONE` | API 실행 모드와 기본 Django 설정 |
| 보안/proxy | `DJANGO_SECURE`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `USE_X_FORWARDED_HOST` | HTTPS, cookie, reverse proxy 설정 |
| `DJANGO_DB_*` / 기본 DB | `DJANGO_DB_NAME`, `DJANGO_DB_USER`, `DJANGO_DB_PASSWORD`, `DJANGO_DB_HOST`, `DJANGO_DB_PORT` | Django 기본 PostgreSQL |
| Dev auto affiliation | `DEV_AUTO_AFFILIATION_ALLOWED`, `DEV_AUTO_AFFILIATION_PREFIX` | 소속 없는 로컬 dev 로그인 사용자의 기본 개발 소속 보장 |
| Dev auto seed | `DEV_AUTO_SEED`, `DEV_SEED_PREFIX` | 로컬 dev API 기동 시 dummy 사용자 보정과 account 권한 요청을 포함한 prefix 기준 더미 데이터 refresh |
| Observer 설정 | `OBSERVER_QUERY_DAYS` | Observer 로그 기본 조회 기간 |
| RACB report URL | `RACB_REPORT_BASE_URL` | RACB 로그 상세 팝업 URL 생성 기준. 비우면 API가 상세 링크를 제공하지 않음 |
| `L3_SPIDER_*` / L3 Spider 파일 데이터/메일 | `L3_SPIDER_DATA_ROOT`, `L3_SPIDER_INDEX_SOURCE`, `L3_SPIDER_MOCK_INDEX_PATH`, `L3_SPIDER_MAX_CHART_POINTS_PER_PANEL`, `L3_SPIDER_MAIL_SENDER`, `L3_SPIDER_MAIL_TARGET_URL` | read-only mount된 `daily_anomaly` Parquet 데이터 경로, 인덱스 source, 개발용 SQLite mock 경로, 차트 sampling 제한, 알림 메일 설정 |
| `FDC_HARD_SPEC_*` / L0 Spider 추천 데이터 | `FDC_HARD_SPEC_DATA_ROOT`, `FDC_HARD_SPEC_PRIORITY_PATH`, `FDC_HARD_SPEC_UNIT_MODEL_PATH`, `FDC_HARD_SPEC_HARD_LIMIT_PATH` | FDC Hard Limit 추천 Parquet 데이터 경로 |
| `TTTM_SPIDER_*` / TTTM Spider 파일 데이터 | `TTTM_SPIDER_ROOT`, `TTTM_SPIDER_DATA_HOST_PATH` | TTTM Spider 원본/계산 결과/참조 데이터의 host mount와 `/data/tttm_spider` 컨테이너 경로 |
| `PM_COMPARISON_*` / PM SPIDER 파일 데이터 | `PM_COMPARISON_DATA_ROOT`, `PM_COMPARISON_DATA_HOST_PATH`, `PM_COMPARISON_MAX_FILES`, `PM_COMPARISON_MAX_META_DIRS` | PM SPIDER raw/score Parquet 데이터의 host mount와 컨테이너 내부 경로, scan 제한 |
| 외부 앱 사용량 API | `EXTERNAL_APP_USAGE_API_URLS`, `EXTERNAL_APP_USAGE_API_TIMEOUT_SECONDS` | 앱별 접속현황에서 수동 동기화할 외부 사용량 API source 목록(JSON)과 timeout |
| `DATA_MOVEMENT_*` / 파일 적재 데이터 | `DATA_MOVEMENT_HOST_PATH`, `DATA_MOVEMENT_FILE_READY_MIN_AGE_SECONDS`, `DATA_MOVEMENT_FILE_READY_STABILITY_SECONDS`, `DATA_MOVEMENT_M_TKIN_PREVENT_DIR`, `DATA_MOVEMENT_CTTTM_WORKORDER_LIST_DIR`, `DATA_MOVEMENT_CT_PROCESS_COMMENT_DIR`, `DATA_MOVEMENT_EQP_STATUS_CHG_DIR`, `DATA_MOVEMENT_M_INTERLOCK_DIR`, `DATA_MOVEMENT_MI_TIP_UPDATE_HIST_DIR`, `DATA_MOVEMENT_RACB_LIST_DIR`, `DATA_MOVEMENT_MES_LINE_MAPPING_INFO_DIR`, `DATA_MOVEMENT_STATION_MASTER_DIR` | FTP 등으로 수신한 파일의 host mount와 테이블별 root 경로. 하위 `incoming/processing` 사용. 최근 수정 파일과 stat 값이 변하는 파일은 이번 적재에서 제외 |
| `FTP_*` / Data Movement FTP | `FTP_USER`, `FTP_PASS`, `FTP_PORT`, `FTP_PASV_ADDRESS`, `FTP_PASV_MIN_PORT`, `FTP_PASV_MAX_PORT` | `data_movement` 업로드용 FTP 계정, 접속 port, passive mode address/port |
| `OIDC_*` / `ADFS_*` / Auth/OIDC | `OIDC_PROVIDER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_ISSUER`, `ADFS_AUTH_URL`, `ADFS_LOGOUT_URL`, `OIDC_REDIRECT_URI`, `OIDC_TOKEN_URL`, `OIDC_JWKS_URL`, `OIDC_CONNECT_TIMEOUT_SECONDS`, `OIDC_READ_TIMEOUT_SECONDS`, `OIDC_JWKS_CACHE_SECONDS`, `ADFS_CER_PATH`, `ALLOWED_REDIRECT_HOSTS` | ADFS id_token 또는 Keycloak code+PKCE/JWKS 로그인 |
| Airflow Web 조회 | `AIRFLOW_BASE_URL`, `AIRFLOW_PUBLIC_BASE_URL`, `AIRFLOW_USERNAME`, `AIRFLOW_PASSWORD`, `AIRFLOW_REQUEST_TIMEOUT_SECONDS` | Django가 Airflow REST API를 호출할 내부 URL·브라우저 링크용 공개 경로·서버 전용 Basic Auth |
| Airflow DAG env | `deploy/airflow/env/k8s.env`의 `AIRFLOW_API_BASE_URL`, `AIRFLOW_TRIGGER_TOKEN`, `AIRFLOW_FAILURE_ALERT_KNOX_IDS`, `KNOX_MESSENGER_API_BASE_URL`, `KNOX_MESSENGER_AUTHORIZATION`, `KNOX_MESSENGER_SYSTEM_ID` | DAG API trigger와 Airflow task 실패 callback용 환경 변수. callback 제목/메모 파일/TTL/timeout 기본값은 DAG 코드에서 관리하며 필요 시 env에서 선택값을 override |
| Airflow DAG runtime options | `L3_SPIDER_MAIL_TRIGGER_LIMIT`, `DATA_MOVEMENT_LOAD_LIMIT`, `DATA_MOVEMENT_LOAD_DRY_RUN`, `DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_LIMIT`, `DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_DRY_RUN`, `DATA_MOVEMENT_CT_PROCESS_COMMENT_CONTINUOUS_DURATION_SECONDS`, `DATA_MOVEMENT_CT_PROCESS_COMMENT_CONTINUOUS_IDLE_SECONDS` | 필요할 때만 외부 env injection으로 조정하는 DAG별 payload/연속 실행 옵션. 일반 schedule과 HTTP timeout은 DAG 코드에서 관리 |
| Emails POP3/OCR | `EMAIL_POP3_*`, `EMAIL_OCR_INTERNAL_TOKEN`, `EMAIL_OCR_CLAIM_LIMIT`, `EMAIL_OCR_LEASE_SECONDS`, `EMAIL_OCR_MAX_ATTEMPTS`, `EMAIL_EXCLUDED_SUBJECT_PREFIXES` | 메일 수집과 OCR worker. dev는 `dummy-ocr-token`을 사용하며 POP3 연결값 미설정 시 수집 trigger가 안전하게 실패합니다. 제목 제외값은 쉼표로 구분하며 `*`는 0글자 이상을 나타내는 wildcard입니다. |
| Drone POP3/Jira/Mail/Messenger | `DRONE_*`, `KNOX_MESSENGER_*` | Drone SOP 수집과 채널별 전송. 환경변수는 Django 시작 시 settings로 한 번 해석하며 runtime에서 다시 읽지 않음 |
| 공용 RAG / Assistant | `RAG_SEARCH_URL`, `RAG_INSERT_URL`, `RAG_DELETE_URL`, `RAG_INDEX_INFO_URL`, `RAG_INDEX_DEFAULT`, `RAG_INDEX_EMAILS`, `RAG_INDEX_LIST`, `RAG_PERMISSION_GROUPS`, `RAG_PUBLIC_GROUP`, `RAG_HEADERS`, `RAG_CHUNK_FACTOR`, `RAG_TIMEOUT_SECONDS`, `RAG_NUM_DOCS`, `ASSISTANT_*` | Emails와 Assistant가 공용 `RAG_*` provider 계약을 사용하고, Assistant 자체 prompt/runtime만 `ASSISTANT_*`를 사용 |
| OpenWebUI | `OPENWEBUI_*` | 일반 Assistant·Email RAG 답변, 대화방 제목, Observer 분석, `ct_process_comment` contents 요약 생성 |
| `MAIL_API_*` / Mail API | `MAIL_API_URL`, `MAIL_API_KEY`, `MAIL_API_SYSTEM_ID`, `MAIL_API_KNOX_ID` | 외부 Mail API 전송. 환경변수는 Django 시작 시 settings로 한 번 해석 |
| MinIO | `MINIO_*` | 메일 asset storage |
| `VITE_*` / Web | `VITE_BACKEND_URL`, `BACKEND_API_URL`, `VITE_SITE_URL` | 브라우저와 container 내부 Django API URL |
| `VITE_PORTAL_*` / Web | `VITE_PORTAL_PMX_URL`, `VITE_PORTAL_MOSAIC_URL`, `VITE_PORTAL_CONFLUENCE_URL` | Portal 전역 네비게이션 외부 링크. 비어 있으면 메뉴 또는 화면에서 숨김/안내 |
| Spider 외부 링크 / Web | `VITE_DEFECT_SPIDER_URL` | `/spider` 허브의 Defect Spider 외부 링크. 비어 있으면 카드가 비활성 안내 상태로 표시 |
| Account UI fixture / Web | `VITE_ACCOUNT_DEV_FIXTURES` | 로컬 계정 화면 예시 데이터. 명시적으로 `1`일 때만 활성화 |

비-Spider Django 설정의 bool 값은 `1/0`, `true/false`, `yes/no`, `on/off`만 허용합니다. int 값은 정수여야 합니다. `EXTERNAL_APP_USAGE_API_URLS`와 `RAG_PERMISSION_GROUPS`는 JSON 배열, `OPENWEBUI_COMMON_HEADERS`, `RAG_HEADERS`, `RAG_CHUNK_FACTOR`는 JSON 객체여야 합니다. 형식이 잘못되면 Django가 default로 대체하지 않고 시작 단계에서 실패합니다. DB 연결은 `DJANGO_DB_*`, OIDC client·issuer·redirect는 `OIDC_*` canonical 키만 사용합니다. `OIDC_PROVIDER`는 `adfs` 또는 `keycloak`만 허용합니다. Keycloak은 공개 authorize/logout/issuer와 API 전용 내부 token/JWKS URL을 분리할 수 있습니다. 구형 `DB_*`, `ADFS_CLIENT_ID`, `GOOGLE_CLIENT_ID`, `ADFS_ISSUER`, `ADFS_REDIRECT_URI` 별칭은 지원하지 않습니다. 외부 공개 API prefix는 `PUBLIC_API_BASE_URL`만 사용하며 `DJANGO_PUBLIC_API_BASE_URL`은 지원하지 않습니다.

### Web profile 환경 변수

- Web 설정은 `deploy/portal/env/<profile>/web.env`만 사용합니다.
- 호스트 Vite dev server는 기존 `import.meta.env`를 사용하고, 운영 정적 Web은 컨테이너 시작 시 생성한 `/runtime-env.js`를 우선 사용합니다.
- runtime config 생성 대상은 `VITE_*`와 Web이 사용하는 명시적 Backend/MinIO key로 제한합니다.
- Airflow Basic Auth는 API profile의 `api.env`에만 두며 Web과 `/runtime-env.js`에 전달하지 않습니다.

### 모니터링 스택

Kubernetes는 kube-prometheus-stack을 사용합니다. [Monitoring 안내](../deploy/monitoring/README.md)에 따라
chart·이미지·Grafana Secret을 준비합니다. 로컬 접속은 `make k8s-grafana`·`make k8s-prometheus`를 사용합니다.
기존 Compose 전용 대시보드·프록시 설정은 제거했습니다. 앱 내부 metric은 별도 instrumentation이 필요합니다.

### 외부 앱 사용량 API

- 여러 외부 사용량 API를 사용할 때는 `EXTERNAL_APP_USAGE_API_URLS`에 명시적 source 목록을 JSON 배열로 설정합니다.
- 예: `[{"sourceName":"m-etch-dx","url":"https://example.test/get/usage"},{"sourceName":"other-system","url":"https://other.example.test/get/usage"}]`
- 각 응답 row는 `date`, `appName`, `accessCount`를 사용하며, `appName`은 앞뒤 공백 제거 후 대문자로 정규화되어 앱 키와 표시명에 사용됩니다.
- `EXTERNAL_APP_USAGE_API_URLS=[]`이면 외부 API 조회를 비활성화합니다.
- 동기화 요청은 최근 365일을 적재하며 일반 사용자는 마지막 시도 후 6시간 동안 다시 실행할 수 없습니다. `access-stats` 관리자 역할은 이 제한을 우회할 수 있습니다.
- 각 source의 `appId`, 날짜, `sourceName` 조합을 갱신하므로 재시도해도 중복 row를 만들지 않습니다.

### L3 Spider 메일 링크 배포 체크

- 운영 서버 배포 전 `deploy/portal/env/prod/api.env`의 `L3_SPIDER_MAIL_TARGET_URL`을 반드시 확인합니다.
- `L3_SPIDER_MAIL_TARGET_URL`은 메일 본문의 `L3 Spider에서 확인` 버튼과 이벤트별 `열기` deep link의 base URL입니다.
- 값은 `/l3_spider`까지 포함한 Web URL로 설정합니다. 예: `https://<운영-host>/l3_spider`
- 비워두면 backend는 `FRONTEND_BASE_URL + /l3_spider`를 사용합니다. 운영에서 `FRONTEND_BASE_URL`이 기대한 Web host인지 함께 확인합니다.

## 파일 데이터 마운트 규칙

API가 직접 읽는 업무 파일 데이터는 신규/변경 시 아래 규칙을 따릅니다.

| 항목 | 규칙 | 예시 |
| --- | --- | --- |
| 컨테이너 경로 | `api` 컨테이너 내부에서는 `/data/<domain>`을 사용합니다. `<domain>`은 lowercase snake_case로 작성합니다. | `/data/pm_spider`, `/data/l3_spider/daily_anomaly` |
| 호스트 경로 env | 로컬 kind host 경로는 `<DOMAIN>_DATA_HOST_PATH`로 지정하고 서버는 PVC·스토리지 입력으로 관리합니다. | `PM_COMPARISON_DATA_HOST_PATH=data/pm_spider` |
| Django data root | Django 설정은 컨테이너 내부 경로를 `<DOMAIN>_DATA_ROOT`로 노출합니다. | `PM_COMPARISON_DATA_ROOT=/data/pm_spider` |
| 권한 | 원본/참조 데이터는 `readOnly: true`로 mount합니다. 앱이 생성/업로드/처리하는 큐성 데이터만 read-write를 허용합니다. | `readOnly: true` |
| 동기화 파일 | API 파일 마운트 변경 시 `local/portal/k8s`, `local/shared/scripts/k8s_config.py`, `deploy/portal/k8s`, `local/portal/env/api.env`, `deploy/portal/env/*/api.env`, 이 문서를 함께 갱신합니다. | PM SPIDER 마운트 변경 |
| 예외 | DB data dir, staticfiles, MinIO bucket 등 서비스 내부 상태는 PVC 또는 서비스 고유 경로를 유지할 수 있습니다. | `minio-data` PVC |

새 마운트에는 `/appdata` 컨테이너 경로를 추가하지 않습니다. 기존 `/appdata` 기반 경로는 해당 데이터 계약을 수정할 때 `/data/<domain>`으로 이동합니다.

PM SPIDER는 단일 `/data/pm_spider` mount 아래에서 `/data/pm_spider/data`와 `/data/pm_spider/result` 구조만 지원합니다.

TTTM Spider는 `${TTTM_SPIDER_DATA_HOST_PATH:-../../../data/tttm_spider}`를 `/data/tttm_spider:ro`로 mount하며 아래 구조를 사용합니다.

- `data/`: line/eqp/chamber/date 기준 원본 Parquet 트리
- `result/`: 사전 계산된 `score_data`와 `decomp_data`
- `reference/`: `sensor_catalog_map.txt`, `oes_wavelength_catalog.txt` 참조 데이터
- `lotwf_index.parquet`: 설비·챔버별 lot/wafer 선택 인덱스

운영에서 `TTTM_SPIDER_DATA_HOST_PATH`를 다른 경로로 override할 때도 `reference/`의 두 파일을 함께 제공해야 합니다.

## 로컬 개발 기본 흐름

`make dev`는 [로컬 실행 안내](../local/README.md)에 따라 한 PC에서 전체 앱을 Kubernetes로 실행합니다.

1. kind control-plane·worker와 별도 Docker PostgreSQL을 준비합니다. 기존 DB는 변경하지 않습니다.
2. `local/shared/compose/k8s-db.yml`이 dashboard·airflow·keycloak DB와 계정을 생성합니다.
3. `local/shared/k8s`에서 앱별 원본을 집계합니다. Portal·Keycloak·MinIO·mock·Headlamp·Traefik은 tailwind-local, Airflow·FTP·Monitoring은 앱별 namespace에 배포합니다.
4. API env는 `local/portal/env/api.env` → `api-k8s.env` → 생성된 `local/shared/runtime/api-overrides.env` 순서로 합성합니다.
5. migration과 seed Job이 완료된 뒤 Portal을 실행합니다. Kubernetes seed에는 `--reset`을 사용하지 않습니다.
6. 인증은 Keycloak, 업무 외부계는 `adfs_dummy`입니다. Airflow trigger token과 관리 계정을 Portal과 공유합니다.
7. `make k8s-smoke`가 대표 인증·챗·메일·FTP·배치·모니터링 시나리오를 검증합니다.

## 로컬 Kubernetes 저장소·설정

`local/shared/env/k8s.env.example`이 공개 설정 계약입니다. 사용자 차이는 같은 디렉터리의 `k8s.env`에 둡니다.
`LOCAL_DB_PORT`, `LOCAL_FTP_PORT`, `LOCAL_FTP_PASSIVE_START`로 포트를 조정합니다.
`LOCAL_RUNTIME_DATA_HOST_PATH`의 기본값은 `data/k8s-local`이며 kind worker의 `/data/local-runtime`에 마운트됩니다.

API의 `/data/data_movement`, `/data/l3_spider/daily_anomaly`, `/data/tttm_spider`, `/data/pm_spider`는
기존 Compose와 동일한 업무 데이터 경로를 사용합니다. 기존 `*_DATA_HOST_PATH`와 `DATA_MOVEMENT_HOST_PATH`를 재사용하고,
참고 데이터는 읽기 전용, FTP 처리 큐는 읽기/쓰기로 연결합니다. Django 컨테이너 경로 계약은 변경하지 않습니다.
MinIO·Airflow 로그·Grafana·Prometheus·Alertmanager는 호스트 디스크를 기반으로 Retain PV를 사용합니다.

생성 자격증명은 `local/shared/runtime/credentials.env`에 0600 권한으로 보관합니다.
`make down`은 kind와 새 DB 컨테이너만 종료하며 PostgreSQL volume·호스트 파일·자격증명은 보존합니다.
DB 컨테이너 주소 변경은 다음 `make dev`에서 EndpointSlice에 반영합니다.

Kubernetes의 일반 기동은 데이터를 reset하지 않습니다.

## 운영/실제 연동 흐름

1. 운영 서버는 `deploy/portal/env/prod` 폴더를 확인합니다.
2. API endpoint와 credential은 해당 profile의 `api.env`에서 관리합니다.
3. API가 Airflow를 조회할 때 쓰는 endpoint와 credential은 API profile에 두고, 실제 Airflow 초기 관리자 계정은 Airflow profile에 둡니다. 두 profile의 사용자 이름과 비밀번호는 같은 값으로 설정해야 합니다.
4. `make prod-profile-env-check`는 K8s API의 DB·Keycloak·MinIO 필수 입력을 검사하며 선택적인 Airflow·RAG 연동은 별도 확인합니다.
5. 모든 API profile은 자신의 `api.env` 하나만 적용합니다.
6. Web의 `VITE_BACKEND_URL`은 reverse proxy 구조에 맞춰 `/` 또는 API origin을 사용합니다.
7. 운영 `deploy/portal/env/prod/*.env`는 Git에서 제외하고 공개 `.example`만 관리합니다. 실제 파일은 안전한 별도 경로로 전달합니다.

## 변경 시 동기화 대상

- Auth 계약 변경: `local/portal/env/api.env`, `deploy/portal/env/*/api.env`, `local/portal/env/web.env`, `deploy/portal/env/*/web.env`, `local/adfs_dummy`, `docs/integrations.md`, `docs/api/auth.md`
- RAG 계약 변경: `local/portal/env/api.env`, `deploy/portal/env/*/api.env`, `local/adfs_dummy`, `docs/integrations.md`, `docs/modules/assistant.md`, `docs/api/assistant.md`
- OpenWebUI 계약 변경: `local/portal/env/api.env`, `deploy/portal/env/*/api.env`, `local/adfs_dummy`, `docs/integrations.md`, `docs/modules/assistant.md`, `docs/api/assistant.md`, `docs/modules/observer.md`, `docs/api/observer.md`
- Mail/Email 계약 변경: `local/portal/env/api.env`, `deploy/portal/env/*/api.env`, `local/adfs_dummy`, `docs/modules/emails.md`, `docs/api/emails.md`
- Drone/Jira/Messenger 계약 변경: `local/portal/env/api.env`, `deploy/portal/env/*/api.env`, `local/adfs_dummy`, `docs/modules/line-dashboard.md`, `docs/api/line-dashboard.md`
- Observer 기준정보/로그 계약 변경: `local/portal/env/api.env`, `deploy/portal/env/*/api.env`, `docs/modules/observer.md`, `docs/api/observer.md`, `docs/data-model.md`
- L3 Spider 데이터 경로 변경: `local/portal/env/api.env`, `deploy/portal/env/prod/api.env`, `local/portal/k8s`, `deploy/portal/k8s`, `local/shared/scripts/k8s_config.py`, `docs/api/l3-spider.md`, `docs/inventory.md`

## PostgreSQL 필수 확장

- API migration 실행 전 대상 PostgreSQL DB에 `pg_trgm` 확장이 준비되어 있어야 합니다.
- 개발 Compose는 `ensure_dev_database`가 개발 DB와 테스트 DB 생성 원본인 `template1`에 확장을 준비합니다.
- 운영 신규 DB는 DB 관리자가 `CREATE EXTENSION IF NOT EXISTS pg_trgm`을 먼저 실행해야 합니다.
# 테스트 전용 Compose

PR CI와 로컬 전체 backend 검증은 `deploy/portal/compose/test.yml`을 사용합니다. 이 구성은 임시 PostgreSQL과 `api-test`만 실행하며 internal Docker network로 외부 ADFS, RAG, Mail, MinIO 연결을 차단합니다. 테스트 환경변수는 `deploy/portal/env/test/api.env`에 있습니다.

```bash
docker compose -f deploy/portal/compose/test.yml run --rm api-test python manage.py test
docker compose -f deploy/portal/compose/test.yml run --rm api-test python manage.py check
docker compose -f deploy/portal/compose/test.yml run --rm api-test python manage.py makemigrations --check --dry-run
```

## 앱 소스와 실행 경로

Portal 소스·이미지 context는 `apps/portal/api`, `apps/portal/web`이며 Airflow 최종 이미지 context는 `apps/airflow`입니다.
배포 입력은 `deploy/<app>/env`, 개발 입력은 `local/<app>/env`에서 계속 관리합니다.
서버 기본 checkout은 배포 정의만 받고 `--with-source`로 앱 소스를 추가합니다. 앱 목록 원본은 `deploy/shared/apps.json`입니다.

Airflow의 Helm 설정은 `deploy/airflow/helm/values.yaml`, 로컬 차이는 `local/airflow/helm/values.yaml`에서 관리합니다.
서버 로그·ODBC 경로는 `k8s.env`의 `LOGS_HOST_PATH`·`ODBC_HOST_PATH`로 지정합니다.

## 최상위 폴더와 Compose 실행 원본

로컬 DB·API 검사는 `local/shared/compose/k8s-db.yml`·`k8s-check.yml`, CI는 `deploy/portal/compose/test.yml`을 사용합니다.
CI DB 초기 입력은 `deploy/portal/test/init-postgres.sql`입니다. 모든 실행 진입점은 루트 Makefile에 있습니다.
Node 의존성은 `apps/portal/web`과 `apps/tooling`에서 개별 관리합니다.
