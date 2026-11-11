# 환경 설정

[참고 자료](../README.md#설정명령) · [문서 홈](../README.md) · [처음 시작하기](../getting-started/01-setup.md)

앱이 읽는 환경변수의 이름·의미·값 형식과 파일 데이터 마운트 계약의 원본입니다.
env 파일의 위치·작성·검사·적용 절차는 실행 환경별 문서가 소유합니다.

| 찾는 내용 | 원본 |
| --- | --- |
| 개발 PC의 env 파일·포트·데이터 경로·생성 credential·설정 합성 순서 | [local 안내](../../local/README.md) |
| 사내 서버의 env 파일 위치·비밀값 관리·검사·Secret 등록 | [앱별 환경설정](../../deploy/shared/docs/configuration/environment.md) |
| 사내 이미지·패키지 미러 주소 | [미러 원본](../../deploy/shared/docs/infrastructure/repositories.md) |
| 설정 이름·값 형식 | 이 문서의 [주요 설정 그룹](#주요-설정-그룹), [시작 단계 검증](#값-형식과-시작-단계-검증) |
| API 파일 데이터 경로·읽기 권한 | 이 문서의 [마운트 규칙](#파일-데이터-마운트-규칙) |
| 외부 연동을 바꿀 때 함께 고칠 파일 | [연동 변경 체크리스트](../concepts/03-integrations.md#연동-변경-체크리스트) |

파일을 수정해도 실행 중인 프로세스에 즉시 반영되지 않습니다. 로컬은 [소스·설정 갱신](../../local/README.md), 서버는 해당 앱의 `deploy` 문서에 따라 반영합니다.

## 공통 원칙

- 외부 시스템 URL·token·credential은 코드에 하드코딩하지 않고 env로 주입합니다.
- 로컬 개발은 public registry·package source와 mock을 사용하며 사내망(`repository.samsungds.net` 등)에 의존하지 않습니다. 사내 서버는 내부 미러만 사용합니다.
- 각 앱은 자신의 env만 읽고 profile 사이에 숨은 상속을 두지 않습니다. 로컬 API는 기본 env → `api-k8s.env` → runtime override → MinIO client credential 순서로 합성합니다.
- Web 공개 설정(`VITE_*`)에는 secret을 넣지 않습니다.

### 승인된 서버 전용 artifact

[배포 지침](../../deploy/AGENTS.md#환경과-데이터-계약)에 따라 서버 빌드 입력에 고정한 사내 artifact URL입니다. 로컬 개발 빌드에는 사용하지 않습니다.

| artifact | 설정 키 | 위치 |
| --- | --- | --- |
| Cloudera Impala ODBC 2.8.3.1008 | `BIGDATAQUERY_ODBC_DEB_URL` | `deploy/airflow/env/build.env`. 주소는 [미러 원본](../../deploy/shared/docs/infrastructure/repositories.md#패키지chartartifact-주소) |

## 주요 설정 그룹

| 그룹 | 대표 변수 | 설명 |
| --- | --- | --- |
| `DJANGO_*` / Django runtime | `ENVIRONMENT`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_TIME_ZONE` | API 실행 모드와 기본 Django 설정 |
| 보안/proxy | `DJANGO_SECURE`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `USE_X_FORWARDED_HOST` | HTTPS, cookie, reverse proxy 설정 |
| `DJANGO_DB_*` / 기본 DB | `DJANGO_DB_NAME`, `DJANGO_DB_USER`, `DJANGO_DB_PASSWORD`, `DJANGO_DB_HOST`, `DJANGO_DB_PORT` | Django 기본 PostgreSQL |
| 개발용 초기 데이터 | `DEV_SEED_PREFIX` | `seed_dev_data`의 더미 데이터 prefix. 로컬 기동 도구가 별도 seed Job을 실행하며 API entrypoint는 `DEV_AUTO_SEED`로 자동 실행하지 않음 |
| Observer 설정 | `OBSERVER_QUERY_DAYS` | Observer 로그 기본 조회 기간 |
| RACB report URL | `RACB_REPORT_BASE_URL` | RACB 로그 상세 팝업 URL 생성 기준. 비우면 API가 상세 링크를 제공하지 않음 |
| `L3_SPIDER_*` / L3 Spider 파일 데이터/메일 | `L3_SPIDER_DATA_ROOT`, `L3_SPIDER_INDEX_SOURCE`, `L3_SPIDER_MOCK_INDEX_PATH`, `L3_SPIDER_MAX_CHART_POINTS_PER_PANEL`, `L3_SPIDER_MAIL_SENDER`, `L3_SPIDER_MAIL_TARGET_URL` | read-only mount된 `daily_anomaly` Parquet 데이터 경로, 인덱스 source, 개발용 SQLite mock 경로, 차트 sampling 제한, 알림 메일 설정 |
| `FDC_HARD_SPEC_*` / L0 Spider 추천 데이터 | `FDC_HARD_SPEC_DATA_ROOT`, `FDC_HARD_SPEC_PRIORITY_PATH`, `FDC_HARD_SPEC_UNIT_MODEL_PATH`, `FDC_HARD_SPEC_HARD_LIMIT_PATH` | FDC Hard Limit 추천 Parquet 데이터 경로 |
| `TTTM_SPIDER_*` / TTTM Spider 파일 데이터 | `TTTM_SPIDER_ROOT`, `TTTM_SPIDER_DATA_HOST_PATH` | TTTM Spider 원본/계산 결과/참조 데이터의 host mount와 `/data/tttm_spider` 컨테이너 경로 |
| `PM_COMPARISON_*` / PM SPIDER 파일 데이터 | `PM_COMPARISON_DATA_ROOT`, `PM_COMPARISON_DATA_HOST_PATH`, `PM_COMPARISON_MAX_FILES`, `PM_COMPARISON_MAX_META_DIRS` | PM SPIDER raw/score Parquet 데이터의 host mount와 컨테이너 내부 경로, scan 제한 |
| 외부 앱 사용량 API | `EXTERNAL_APP_USAGE_API_URLS`, `EXTERNAL_APP_USAGE_API_TIMEOUT_SECONDS` | 앱별 접속현황에서 수동 동기화할 외부 사용량 API source 목록(JSON)과 timeout |
| `DATA_MOVEMENT_*` / 파일 적재 데이터 | `DATA_MOVEMENT_HOST_PATH`, `DATA_MOVEMENT_FILE_READY_MIN_AGE_SECONDS`, `DATA_MOVEMENT_FILE_READY_STABILITY_SECONDS`, `DATA_MOVEMENT_M_TKIN_PREVENT_DIR`, `DATA_MOVEMENT_CTTTM_WORKORDER_LIST_DIR`, `DATA_MOVEMENT_CT_PROCESS_COMMENT_DIR`, `DATA_MOVEMENT_EQP_STATUS_CHG_DIR`, `DATA_MOVEMENT_M_INTERLOCK_DIR`, `DATA_MOVEMENT_MI_TIP_UPDATE_HIST_DIR`, `DATA_MOVEMENT_RACB_LIST_DIR`, `DATA_MOVEMENT_MES_LINE_MAPPING_INFO_DIR`, `DATA_MOVEMENT_STATION_MASTER_DIR` | FTP 등으로 수신한 파일의 host mount와 테이블별 root 경로. 하위 `incoming/processing` 사용. 최근 수정 파일과 stat 값이 변하는 파일은 이번 적재에서 제외 |
| Data Movement FTP 계정 | `FTP_USER`, `FTP_PASS` | 운영은 `FTP_CREDENTIAL_FILE`로 선택한 계정 파일에서 Secret으로 전달. 로컬은 고정 사용자와 생성된 credential 사용 |
| 로컬 FTP 접속 | `LOCAL_FTP_PORT`, `LOCAL_FTP_PASSIVE_START` | `local/shared/env/k8s.env`의 호스트 접속 포트와 연속 4개 Passive 포트. 운영 제어 포트는 시작 스크립트·DaemonSet의 6380이며, Passive 포트는 manifest의 `PASV_MIN_PORT`·`PASV_MAX_PORT`, 주소는 `status.hostIP`로 주입 |
| FTP 서버 배포 | `FTP_ENV`, `FTP_IMAGE`, `IMAGE_PULL_SECRET`, `FTP_ALLOW_CONTROL_PLANE` | `FTP_ENV`로 선택한 운영 env(기본 `deploy/ftp/env/prod.env`)에서 고정 tag/digest 이미지와 선택 pull Secret을 읽어 `make ftp-check`·`make ftp-up`에 적용. 사내 미러 기본값. `FTP_ALLOW_CONTROL_PLANE`의 기본값·생략값은 true이며 선택한 control plane의 역할 NoSchedule을 허용. false를 명시하면 control plane 선택 거부. 로그인 계정은 별도 `FTP_CREDENTIAL_FILE` |
| `OIDC_*` / Auth/OIDC | `OIDC_PROVIDER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_ISSUER`, `OIDC_AUTH_URL`, `OIDC_LOGOUT_URL`, `OIDC_REDIRECT_URI`, `OIDC_TOKEN_URL`, `OIDC_JWKS_URL`, `OIDC_CONNECT_TIMEOUT_SECONDS`, `OIDC_READ_TIMEOUT_SECONDS`, `OIDC_JWKS_CACHE_SECONDS`, `ALLOWED_REDIRECT_HOSTS` | Keycloak code+PKCE/JWKS 로그인과 세션별 권한 |
| Airflow Web 조회 | `AIRFLOW_BASE_URL`, `AIRFLOW_PUBLIC_BASE_URL`, `AIRFLOW_USERNAME`, `AIRFLOW_PASSWORD`, `AIRFLOW_REQUEST_TIMEOUT_SECONDS` | Django가 Airflow REST API를 호출할 내부 URL·브라우저 링크용 공개 URL·서버 계정의 JWT 발급과 API v2 Bearer 인증. 사용자·비밀번호는 Airflow env의 실제 관리자 계정과 같은 값 |
| Airflow DAG env | `deploy/airflow/env/k8s.env`의 `AIRFLOW_API_BASE_URL`, `AIRFLOW_TRIGGER_TOKEN`, `AIRFLOW_FAILURE_ALERT_KNOX_IDS`, `KNOX_MESSENGER_API_BASE_URL`, `KNOX_MESSENGER_AUTHORIZATION`, `KNOX_MESSENGER_SYSTEM_ID` | DAG API trigger와 Airflow task 실패 callback용 환경 변수. callback 제목/메모 파일/TTL/timeout 기본값은 DAG 코드에서 관리하며 필요 시 env에서 선택값을 override |
| Airflow DAG runtime options | `L3_SPIDER_MAIL_TRIGGER_LIMIT`, `DATA_MOVEMENT_LOAD_LIMIT`, `DATA_MOVEMENT_LOAD_DRY_RUN`, `DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_LIMIT`, `DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_DRY_RUN`, `DATA_MOVEMENT_CT_PROCESS_COMMENT_CONTINUOUS_DURATION_SECONDS`, `DATA_MOVEMENT_CT_PROCESS_COMMENT_CONTINUOUS_IDLE_SECONDS` | 필요할 때만 외부 env injection으로 조정하는 DAG별 payload/연속 실행 옵션. 일반 schedule과 HTTP timeout은 DAG 코드에서 관리 |
| Emails POP3/OCR | `EMAIL_POP3_*`, `EMAIL_OCR_INTERNAL_TOKEN`, `EMAIL_OCR_CLAIM_LIMIT`, `EMAIL_OCR_LEASE_SECONDS`, `EMAIL_OCR_MAX_ATTEMPTS`, `EMAIL_EXCLUDED_SUBJECT_PREFIXES` | 메일 수집과 OCR worker. dev는 `dummy-ocr-token`을 사용하며 POP3 연결값 미설정 시 수집 trigger가 안전하게 실패합니다. 제목 제외값은 쉼표로 구분하며 `*`는 0글자 이상을 나타내는 wildcard입니다. |
| Drone POP3/Jira/Mail/Messenger | `DRONE_*`, `KNOX_MESSENGER_*` | Drone SOP 수집과 채널별 전송. 환경변수는 Django 시작 시 settings로 한 번 해석하며 runtime에서 다시 읽지 않음 |
| 공용 RAG / Assistant | `RAG_SEARCH_URL`, `RAG_INSERT_URL`, `RAG_DELETE_URL`, `RAG_INDEX_INFO_URL`, `RAG_INDEX_DEFAULT`, `RAG_INDEX_EMAILS`, `RAG_INDEX_LIST`, `RAG_PERMISSION_GROUPS`, `RAG_PUBLIC_GROUP`, `RAG_HEADERS`, `RAG_CHUNK_FACTOR`, `RAG_TIMEOUT_SECONDS`, `RAG_NUM_DOCS`, `ASSISTANT_*` | Emails와 Assistant가 공용 `RAG_*` provider 계약을 사용하고, Assistant 자체 prompt/runtime만 `ASSISTANT_*`를 사용 |
| OpenWebUI | `OPENWEBUI_*` | 일반 Assistant·Email RAG 답변, 대화방 제목, Observer 분석, `ct_process_comment` contents 요약 생성 |
| `MAIL_API_*` / Mail API | `MAIL_API_URL`, `MAIL_API_KEY`, `MAIL_API_SYSTEM_ID`, `MAIL_API_KNOX_ID` | 외부 Mail API 전송. 환경변수는 Django 시작 시 settings로 한 번 해석 |
| MinIO | `MINIO_*` | 공용 객체 저장소. 운영 endpoint는 `http://minio.minio.svc.cluster.local:9000`, 앱별 키는 해당 앱 env |
| `VITE_*` / Web | `VITE_BACKEND_URL`, `BACKEND_API_URL`, `VITE_SITE_URL` | 브라우저와 container 내부 Django API URL |
| `VITE_PORTAL_*` / Web | `VITE_PORTAL_PMX_URL`, `VITE_PORTAL_MOSAIC_URL`, `VITE_PORTAL_CONFLUENCE_URL` | Portal 전역 네비게이션 외부 링크. 비어 있으면 메뉴 또는 화면에서 숨김/안내 |
| Spider 외부 링크 / Web | `VITE_DEFECT_SPIDER_URL` | `/spider` 허브의 Defect Spider 외부 링크. 비어 있으면 카드가 비활성 안내 상태로 표시 |
| Account UI fixture / Web | `VITE_ACCOUNT_DEV_FIXTURES` | 로컬 계정 화면 예시 데이터. 명시적으로 `1`일 때만 활성화 |

### 값 형식과 시작 단계 검증

비-Spider Django 설정은 다음 형식을 사용합니다. 형식이 잘못되면 기본값으로 대체하지 않고 Django 시작 단계에서 실패합니다.

| 설정 유형 | 허용 형식 |
| --- | --- |
| bool | `1/0`, `true/false`, `yes/no`, `on/off` |
| int | 정수 |
| `EXTERNAL_APP_USAGE_API_URLS`, `RAG_PERMISSION_GROUPS` | JSON 배열 |
| `OPENWEBUI_COMMON_HEADERS`, `RAG_HEADERS`, `RAG_CHUNK_FACTOR` | JSON 객체 |

### 현재 인증·DB 설정

DB 연결은 `DJANGO_DB_*`, OIDC client·issuer·redirect는 `OIDC_*` 키만 사용합니다.
`OIDC_PROVIDER`는 `keycloak`만 허용합니다. Keycloak은 공개 authorize/logout/issuer와
API 전용 내부 token/JWKS URL을 분리할 수 있습니다.

앱 권한은 Keycloak client 역할만으로 판정합니다. `deptid`는 신원 정보이며 내부 부서 판정 env는 사용하지 않습니다.

`PUBLIC_API_BASE_URL`은 Django 설정으로 읽고 운영 env 검사에서 URL 형식을 확인합니다.
현재 API 라우팅이나 URL 생성에는 사용하지 않습니다. 업무 API 경로는 `api/urls.py`의 `/api/v1/`이며,
브라우저의 API 접속 주소는 Web의 `VITE_BACKEND_URL`과 reverse proxy 설정으로 맞춥니다.

### Web profile 환경 변수

- Web 설정은 로컬에서 `local/portal/env/web.env`, 운영에서 `deploy/portal/env/prod/web.env`를 사용합니다.
- 호스트 Vite dev server는 `import.meta.env`를 사용하며 `local/portal/env/web.env`를 자동으로 읽지 않습니다. 실행 환경변수 또는 `apps/portal/web/.env.development.local`로 `VITE_*` 값을 전달합니다. API·로그인 연결 조건은 [Web 실행 안내](../../apps/portal/web/README.md#실행하기)를 따릅니다.
- 정적 Web은 컨테이너 시작 시 생성한 `/runtime-env.js`를 우선 사용합니다. 설정 변경은 env 적용과 컨테이너 재시작이 필요합니다.
- runtime config 생성 대상은 `VITE_*`와 Web이 사용하는 명시적 Backend/MinIO key로 제한합니다.
- Airflow 서버 계정은 API profile의 `api.env`에서 관리하고, 발급 token은 Django 서버 메모리에서만 사용합니다. 두 정보는 Web과 `/runtime-env.js`에 전달하지 않습니다.

### 외부 앱 사용량 API

- 여러 외부 사용량 API를 사용할 때는 `EXTERNAL_APP_USAGE_API_URLS`에 명시적 source 목록을 JSON 배열로 설정합니다.
- 예: `[{"sourceName":"m-etch-dx","url":"https://example.test/get/usage"},{"sourceName":"other-system","url":"https://other.example.test/get/usage"}]`
- 각 응답 row는 `date`, `appName`, `accessCount`를 사용하며, `appName`은 앞뒤 공백 제거 후 대문자로 정규화되어 앱 키와 표시명에 사용됩니다.
- `EXTERNAL_APP_USAGE_API_URLS=[]`이면 외부 API 조회를 비활성화합니다.
- 동기화 요청은 최근 365일을 적재하며 일반 사용자는 마지막 시도 후 6시간 동안 다시 실행할 수 없습니다. Keycloak `access-stats` 관리자 역할(Portal 관리자 포함)은 이 제한을 우회할 수 있습니다.
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

로컬 kind는 `local/shared/env/k8s.env`의 `TTTM_SPIDER_DATA_HOST_PATH`로 호스트 디렉터리를 지정합니다.
기본값은 저장소 루트의 `data/tttm_spider`이며 API의 `/data/tttm_spider`에 읽기 전용으로 연결합니다.
운영 API 기본 볼륨은 `emptyDir`입니다. 운영에서는 해당 볼륨을 실제 데이터가 있는 PVC 등으로 교체하고
`/data/tttm_spider`에 읽기 전용으로 연결합니다. 이 호스트 경로 변수를 운영 API env에 추가해도 마운트는 바뀌지 않습니다.
두 환경의 데이터 디렉터리 구조는 다음과 같습니다.

- `data/`: line/eqp/chamber/date 기준 원본 Parquet 트리
- `result/`: 사전 계산된 `score_data`와 `decomp_data`
- `reference/`: `sensor_catalog_map.txt`, `oes_wavelength_catalog.txt` 참조 데이터
- `lotwf_index.parquet`: 설비·챔버별 lot/wafer 선택 인덱스

호스트 디렉터리나 운영 볼륨을 준비할 때 `reference/`의 두 파일도 함께 제공해야 합니다.

## PostgreSQL 필수 확장

API migration 전 대상 DB에 `pg_trgm` 확장이 필요합니다. 개발 Compose는 `ensure_dev_database`가 개발 DB와 테스트 DB 생성 원본인 `template1`에 확장을 준비합니다.
운영 DB의 준비는 [Portal 설치](../../deploy/portal/docs/01-install.md)를 따릅니다.

## 테스트 전용 Compose

독립 CI API 검사는 `deploy/portal/compose/test.yml`과 `deploy/portal/env/test/api.env`를 사용합니다.
임시 PostgreSQL(초기 입력 `deploy/portal/test/init-postgres.sql`)과 `api-test`를 실행하며 외부 서비스 연결은 internal Docker network로 차단합니다.
실행 명령은 [독립 CI 검사](../getting-started/02-usage.md#독립-ci-검사)를 따릅니다.
