# 운영/개발 명령

이 문서는 로컬 실행, 테스트, 마이그레이션 확인, management command를 정리합니다.

## 실행 진입점

일반 작업에서는 root의 `make` target을 사용합니다.
root compose 파일은 Makefile이 감싸는 실행 구현이고, `compose/` 아래 파일은 내부 조립용입니다.

| 환경 | 기본 명령 | 용도 | dependency source |
| --- | --- | --- | --- |
| `dev` | `make dev` | 로컬 개발 전용 | public registry/package source |
| `oidc` | `make oidc` | 사내 OIDC 검증/스테이징 | internal mirror |
| `prod` | `make prod` | 운영 compose 조립 | internal mirror |

`dev`는 로컬 PC에서만 사용하는 개발 환경입니다.
`oidc`와 `prod`는 Docker image와 package manager source를 내부 mirror로 고정합니다.

## app / infra 구분

| 그룹 | 포함 서비스 | 설명 |
| --- | --- | --- |
| `app` | API, Web, Nginx, MinIO, MinIO init | 실제 앱 실행에 필요한 서비스 |
| `dev app` 추가 | Keycloak, Keycloak PostgreSQL, dummy RAG/LLM/Mail/Jira | 로컬 인증과 외부계 대체 서비스 |
| `infra` | Airflow DB, Airflow init/webserver/scheduler, FTP | 데이터 적재와 Airflow DAG 검증용 기반 서비스 |

로컬 개발 기본 실행:

```bash
make dev
```

`make dev`는 Portal app stack과 Work Hub의 Grist·접근 동기화 worker를 함께 실행하고 Navbar 메뉴를 활성화합니다. Portal만 필요한 경우에는 `make dev-app-up`을 사용합니다.

app만 조작:

```bash
make dev-app-up
make dev-app-build
make dev-app-down
make oidc-app-up
make oidc-app-build
make oidc-app-down
make prod-app-up
make prod-app-build
make prod-app-down
```

Airflow/FTP 기반 데이터 적재 작업이 필요하면 infra를 별도로 조작합니다.
OIDC/prod infra에는 monitoring 서비스도 함께 포함됩니다.

```bash
make dev-infra-up
make dev-infra-build
make dev-infra-down
make oidc-infra-up
make oidc-infra-build
make oidc-infra-down
make prod-infra-up
make prod-infra-build
make prod-infra-down
```

OIDC/prod compose에는 Airflow/FTP 외에 monitoring 서비스도 포함됩니다.

주요 주소:

| 서비스 | 주소 |
| --- | --- |
| Web | `http://localhost:3000` |
| API | `http://localhost:8000` |
| Nginx | `http://localhost` |
| Keycloak | `http://localhost:8180` |
| Dummy RAG/LLM/Mail/Jira | `http://localhost:9102` |
| MinIO | `http://localhost:9000`, `http://localhost:9001` |

## 프론트 명령

```bash
npm run web:dev
npm run web:build
npm run web:lint
npm run agent:audit
npm run agent:audit:docs
npm run agent:audit:web-boundary
npm run agent:audit:ui
```

## 백엔드 검증

백엔드는 Docker Compose `api` 컨테이너 기준입니다.

```bash
make check-api
make test-api
make makemigrations-check
```

## Management command

| Command | 설명 |
| --- | --- |
| `check_access_permission_integrity` | `--phase` 기준 migration 전 legacy 또는 적용 후 고정 역할·앱별 소속 범위 정합성 점검 |
| `migrate_legacy_access_to_keycloak` | 현재 유효한 기본 소속과 Portal·앱 user/admin 역할을 dry-run 기본으로 이관하고 선택적으로 비교 |
| `audit_keycloak_cutover` | Account 테이블 row count/checksum과 DB backup·realm export·복원 시험 증적을 함께 검증 |
| `backfill_assistant_run_access` | legacy Assistant Run·메시지·요약·제목의 Profile과 `access_requirements`를 dry-run 가능한 batch로 보강 |
| `ensure_dev_database` | dev DB와 테스트 DB 생성 원본에 필수 PostgreSQL extension 생성 |
| `process_email_outbox` | EmailOutbox RAG 작업 처리 |
| `seed_dev_data` | 로컬 개발용 더미 사용자 보정 및 더미 데이터 통합 refresh |
| `seed_appstore_dummy_data` | 로컬 개발용 Appstore 순서 관리 더미 앱 생성 |
| `seed_dummy_emails` | 로컬 개발용 더미 Email 데이터 생성 |
| `load_m_tkin_prevent` | `m_tkin_prevent` incoming 파일 적재 |
| `load_ctttm_workorder_list` | `ctttm_workorder_list` incoming 파일 적재 |
| `load_ct_process_comment` | `ct_process_comment` incoming 파일 적재 |
| `summarize_ct_process_comment` | `ct_process_comment` OpenWebUI 요약 처리 |
| `load_eqp_status_chg` | `eqp_status_chg` incoming 파일 적재 |
| `load_m_interlock` | `m_interlock` incoming 파일 interlock_no 기준 upsert |
| `load_mi_tip_update_hist` | `mi_tip_update_hist` incoming 파일 적재 |
| `load_racb_list` | `racb_list` incoming 파일 적재 |
| `load_mes_line_mapping_info` | `mes_line_mapping_info` incoming 파일 전체 교체 적재 |
| `load_station_master` | `station_master` incoming 파일 전체 교체 적재 |
| `import_l3_spider_line_name_rules` | L3 Spider line name 규칙 CSV를 검증해 DB 규칙으로 교체 적재 |
| `seed_drone_dummy_data` | 로컬 개발용 Drone SOP 더미 데이터 생성 |
| `seed_drone_targets_from_file` | JSON/CSV 기준 Drone SOP/발송 이력/알림 설정 초기화 후 target/channel/recipient seed |
| `prune_drone_sop` | 보관 기간 초과 Drone SOP 데이터 정리 |
| `purge_drone_sop` | Drone SOP 데이터 전체 삭제 또는 dry-run 확인 |
| `configure_grist_scope` | 소속과 Grist workspace/document/table ID mapping 등록 후 ACL Outbox 적재(`doc_id` 교체 불가), 선택적으로 document 전용 Webhook Authorization 출력 |
| `audit_grist_schema` | Work Hub Grist table의 필수 column과 type 계약 검사 |
| `sync_grist_equipment` | Observer 설비를 Grist Equipment에 upsert/archive |
| `sync_grist_access` | 비활성 소속을 포함한 Portal 사용자·역할을 Grist document ACL로 전체 동기화 |
| `process_grist_access_sync` | 전용 worker에서 Grist 역할 Outbox 처리, 최대 5분 Keycloak ACL 정합성 복구, 완료 이력 30일·실패 Webhook receipt 90일 기준 정리 |
| `seed_grist_demo` | 로컬 `DEV_ALPHA`용 Grist schema·record·Webhook·mapping 멱등 생성 |

실행 예시:

```bash
docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate --noinput
docker compose -f docker-compose.dev.yml exec -T api python manage.py check_access_permission_integrity --phase post-migration
docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate_legacy_access_to_keycloak --emergency-sabun <사번>
docker compose -f docker-compose.dev.yml exec -T api python manage.py backfill_assistant_run_access --dry-run --batch-size 500
docker compose -f docker-compose.dev.yml exec -T api python manage.py ensure_dev_database
docker compose -f docker-compose.dev.yml exec -T api python manage.py process_email_outbox
docker compose -f docker-compose.dev.yml exec -T api python manage.py seed_dev_data --reset --prefix DEV
docker compose -f docker-compose.dev.yml exec -T api python manage.py seed_appstore_dummy_data --reset --prefix DEV
docker compose -f docker-compose.dev.yml exec -T api python manage.py seed_dummy_emails
docker compose -f docker-compose.dev.yml exec -T api python manage.py load_m_tkin_prevent
docker compose -f docker-compose.dev.yml exec -T api python manage.py load_ctttm_workorder_list
docker compose -f docker-compose.dev.yml exec -T api python manage.py load_ct_process_comment
docker compose -f docker-compose.dev.yml exec -T api python manage.py summarize_ct_process_comment
docker compose -f docker-compose.dev.yml exec -T api python manage.py load_eqp_status_chg
docker compose -f docker-compose.dev.yml exec -T api python manage.py load_m_interlock
docker compose -f docker-compose.dev.yml exec -T api python manage.py load_mi_tip_update_hist
docker compose -f docker-compose.dev.yml exec -T api python manage.py load_racb_list
docker compose -f docker-compose.dev.yml exec -T api python manage.py load_mes_line_mapping_info
docker compose -f docker-compose.dev.yml exec -T api python manage.py load_station_master
docker compose -f docker-compose.dev.yml exec -T api python manage.py seed_drone_dummy_data --prefix DEMO --reset
docker compose -f docker-compose.dev.yml exec -T api python manage.py seed_drone_targets_from_file --file /app/config/drone_targets.json --dry-run
docker compose -f docker-compose.dev.yml exec -T api python manage.py prune_drone_sop
docker compose -f docker-compose.dev.yml exec -T api python manage.py purge_drone_sop --dry-run
docker compose -f docker-compose.dev.yml exec -T api python manage.py configure_grist_scope --help
docker compose -f docker-compose.dev.yml exec -T api python manage.py audit_grist_schema
docker compose -f docker-compose.dev.yml exec -T api python manage.py sync_grist_equipment --all --dry-run
docker compose -f docker-compose.dev.yml exec -T api python manage.py sync_grist_access --all --dry-run
docker compose -f docker-compose.dev.yml exec -T api python manage.py process_grist_access_sync
docker compose -f docker-compose.dev.yml exec -T api python manage.py seed_grist_demo
```

## Keycloak 권한 전환

Portal은 `사내 OIDC → Keycloak → Django session` 순서로 인증합니다. 운영 Keycloak은 Portal Compose와 분리하며, Portal에는 realm/client endpoint와 secret만 env로 주입합니다. 사내 OIDC의 `sabun` mapper는 서명된 불변 고유 식별자로 구성합니다. Keycloak access token 수명은 300초입니다.

realm은 `/affiliations/<소속>/<viewer|member|manager>` group과 Portal client의 `portal-user/admin`, `<scope>-user/admin` role을 사용합니다. 사용자는 기본 소속 role group을 정확히 하나만 가져야 합니다. 일반 app user는 자기 기본 소속만, app admin은 해당 앱 전체 데이터를 조회합니다. 지정된 비상 계정 하나만 모든 `*-admin` role을 가지며 Django superuser는 권한 우회로 사용하지 않습니다.

전환 순서는 다음과 같습니다.

1. 읽기 전용 dry-run을 실행해 누락·중복 사용자와 비상 계정 수를 검증하고 출력 `checksum`을 보관합니다. pending, denied, 만료 grant, 추가 데이터 범위와 상세 감사 이력은 계획에 포함되지 않습니다.
2. `--apply --compare`로 같은 계획을 멱등 반영하고 legacy/Keycloak group·client role이 일치하는지 확인합니다.
3. 기존 Work Hub mapping마다 `configure_grist_scope --keycloak-group-id ... --affiliation-name ...`를 실행합니다. 기존 `legacy-affiliation:<id>` mapping은 같은 document에서 group ID만 교체되며 `doc_id`는 바뀌지 않습니다.
4. API code flow/JWKS/refresh, 일반 사용자와 각 scope admin 접근, Work Hub forward-auth와 ACL을 smoke test합니다.
5. Keycloak role 변경·회수가 최대 5분 안에 Portal과 Grist에 반영되는지 확인합니다. Admin API 조회가 5분 이상 실패하면 worker가 관리 ACL을 비워 fail-closed 처리합니다.

```bash
docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate_legacy_access_to_keycloak --emergency-sabun <사번>
docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate_legacy_access_to_keycloak --emergency-sabun <사번> --apply --compare
```

실제 cutover 직전에는 API와 권한 worker를 중지하고 DB backup, Account row count/checksum, Keycloak realm export와 별도 Keycloak/PostgreSQL에서의 복원 시험을 완료합니다. `audit_keycloak_cutover`는 세 증적 파일이 모두 존재하고 비어 있지 않을 때만 manifest를 출력합니다. 경로는 API container 내부 경로로 전달합니다.

```bash
docker compose -f docker-compose.dev.yml exec -T airflow-postgres pg_dump -U airflow -Fc dashboard -f /tmp/portal-before-keycloak.dump
# 운영 Keycloak 절차에 따라 realm export 후, 격리된 Keycloak 26.7.1과 별도 PostgreSQL에 import하고 로그인/group/role 조회 결과를 증적 파일로 남깁니다.
docker compose -f docker-compose.dev.yml exec -T api python manage.py audit_keycloak_cutover \
  --emergency-sabun <사번> \
  --database-backup /evidence/portal-before-keycloak.dump \
  --realm-export /evidence/portal-realm.json \
  --realm-restore-evidence /evidence/realm-restore-test.txt
```

manifest와 권한 비교가 일치한 뒤에만 Account non-User 테이블 제거 migration을 별도 배포합니다. 제거 migration은 rollback 불가능한 단계이므로 이 저장소의 전환 branch에서는 실행하지 않으며, backup과 realm 복원 시험이 없는 환경에서는 절대 적용하지 않습니다. 전환 후 Account 쓰기 API·관리 화면은 제공하지 않고 `/settings/account`만 내 정보·소속·역할 조회용으로 유지합니다.

Assistant Runtime v2 배포는 nullable schema migration을 먼저 적용한 뒤 `--dry-run` 집계를
검토하고 command를 실행합니다. command는 checkpoint 파일로 중단·재개할 수 있고 동일
batch를 다시 실행해도 같은 synthetic Run 식별자를 사용합니다. 충돌하거나 분류할 수 없는
legacy 데이터는 `legacy-unresolved`로 유지해 노출하지 않습니다. 완료 보고서에서 미연결
메시지가 없음을 확인하기 전에는 non-null 제약을 강화하지 않습니다. 제품 실행 endpoint는
표준 Turn만 제공하므로 backfill 진행 여부와 관계없이 과거 데이터가 실행 경로로 유입되지 않습니다.
### Work Hub 시험 적용과 원복

```bash
make work-hub-up
make work-hub-down
```

개발 시험의 `make work-hub-down`은 Work Hub를 즉시 중지합니다. Grist container만 단독 확인할 때는 `docker compose -f docker-compose.dev.yml --profile work-hub up -d grist`를 사용할 수 있지만, 이 명령은 Portal의 Work Hub 플래그를 켜지 않습니다.

OIDC·prod에서는 Grist를 새 서버 `10.172.117.91`에 분리합니다. 먼저 새 서버에서 session secret을 배포 환경으로 주입하고 Grist, API key initializer, 전용 Nginx를 기동합니다.

```bash
GRIST_SESSION_SECRET='<배포 비밀값>' make grist-remote-config
GRIST_SESSION_SECRET='<배포 비밀값>' make grist-remote-up
curl -fsS http://10.172.117.91/status
```

`make grist-remote-up`은 key 디렉터리를 만들고 현재 배포 사용자의 UID/GID를 initializer에 자동 전달합니다. 첫 기동 후 해당 사용자 소유 `0600`으로 생성된 `data/work_hub_secrets/remote/grist_api_key` 값을 기존 Portal 서버의 배포 secret `GRIST_API_KEY`로 전달한 뒤 Portal 측 target을 실행합니다.

```bash
make oidc-work-hub-up
make prod-work-hub-up
```

`make prod-work-hub-up`은 원격 Grist API key가 없으면 중단하고, 운영 API·Web image를 함께 빌드한 뒤 구버전 API와 `work-hub-access-worker`를 중지합니다. 이어 같은 API image의 one-off container로 `migrate --noinput`을 실행하며 migration이 실패하면 신버전을 기동하지 않습니다. OIDC도 key 누락 시 중단합니다. 이 target들은 새 서버의 Grist container를 생성하거나 삭제하지 않습니다.

`make oidc-app-up`과 `make prod-app-up`은 Work Hub를 사용하지 않는 배포를 위해 `work-hub-access-worker`를 제외합니다.

사용자 session 정리 유예가 필요한 운영 원복에서는 양쪽 서버를 함께 비활성화합니다. Portal 측 target은 UI·Webhook·worker 쓰기를 끄고, 새 서버 target은 Grist 본문·widget 접근을 503으로 차단합니다. `down -v`는 사용하지 않습니다.

```bash
# OIDC(stage)
make oidc-work-hub-disable
# 새 Grist 서버
make grist-remote-disable
# session 정리 유예 후
make oidc-work-hub-down
make grist-remote-down

# 운영
make prod-work-hub-disable
# 새 Grist 서버
make grist-remote-disable
# session 정리 유예 후
make prod-work-hub-down
make grist-remote-down
```

Portal의 2단계 target은 `work-hub-access-worker`를 제거하고 API·Web·Nginx를 세 플래그가 모두 꺼진 상태로 재생성합니다. 새 서버의 `grist-remote-down`은 Grist·initializer·원격 Nginx container만 제거합니다. named `tailwind_grist_remote_data` volume과 bootstrap key 파일은 보존되므로 언제든 같은 설정으로 다시 기동할 수 있습니다. schema, backup, restore와 Portal account forward-auth 설정은 `docs/modules/work-hub.md`를 따릅니다.

Keycloak 전환 뒤에는 Portal에서 권한을 자동 생성하거나 변경하지 않습니다. 최초 및 비상
관리 권한은 지정된 Keycloak 계정의 `portal-admin`과 앱별 `*-admin` client role로만
부여합니다. Django superuser, 기존 Account 권한 관리 API와 관리 화면은 권한 우회 수단이
아닙니다.

로컬 dev 사용자의 소속과 역할은 `deploy/keycloak/realm-portal.json`에서 관리합니다.
`DEV_AUTO_SEED=1`의 업무 더미 데이터 refresh는 유지하지만 Keycloak 사용자를 Django
superuser로 승격하거나 Account 권한 row를 자동 생성하지 않습니다. 운영에서는 realm
변경을 Portal 배포와 분리하고, 변경 전 realm export와 복원 시험을 완료합니다.

## Data Movement Airflow DAG

`airflow/dags/data_movement_file_load.py`는 기본 1분 주기로 아래 파일 적재 endpoint를 호출합니다.

```text
POST /api/v1/data-movement/m_tkin_prevent/load/
POST /api/v1/data-movement/ctttm_workorder_list/load/
POST /api/v1/data-movement/ct_process_comment/load/
POST /api/v1/data-movement/eqp_status_chg/load/
POST /api/v1/data-movement/m_interlock/load/
POST /api/v1/data-movement/mi_tip_update_hist/load/
POST /api/v1/data-movement/racb_list/load/
POST /api/v1/data-movement/mes_line_mapping_info/load/
POST /api/v1/data-movement/station_master/load/
```

`ct_process_comment`는 workorder 목록을 참조하므로 DAG에서 `ctttm_workorder_list` 이후 실행됩니다.
모든 Airflow DAG는 `max_active_runs=1`로 같은 DAG의 실행 회차가 겹치지 않게 합니다.
task별 `max_active_tasks`와 공용 pool은 지정하지 않으며 `default_pool`은 무제한 slots인 `-1`로 초기화합니다.
pool 외의 task 동시 실행 수는 Airflow 기본 전역 설정을 따릅니다.
`eqp_status_chg`는 `/data/data_movement/m_eqp_status_chg/incoming/*m_eqp_status_chg*.csv.deflate` 파일을 `eqp_event_key` 기준으로 upsert하고 180일 retention을 적용합니다.
`m_interlock`은 `/data/data_movement/m_interlock/incoming/m_interlock_<LineID>_<YYYYMMDD>_<HHMM>.csv.deflate` 파일을 `interlock_no` 기준으로 incremental upsert하며 빈 key row는 제외합니다.
`mi_tip_update_hist`는 `/data/data_movement/mi_tip_update_hist/incoming/*mi_tip_update_hist*.csv.deflate` 파일을 TIP timeline 조회용 row로 적재합니다.
`racb_list`는 `/data/data_movement/racb_list/incoming/*racb_list*.csv.deflate` 파일을 `c_racb_id` 최신 row 기준으로 설비별 `eqp_cb` row로 펼쳐 적재합니다.
`mes_line_mapping_info`는 `/data/data_movement/mes_line_mapping_info/incoming/*_MES_MAPPING_INFO_*.csv.deflate` 파일을 테이블 전체 snapshot으로 적재합니다.
`station_master`는 `/data/data_movement/station_master/incoming/*_STATION_MASTER_*.csv.deflate` 파일을 테이블 전체 snapshot으로 적재합니다.
파일 적재 DAG는 코드에 고정된 `*/1 * * * *` schedule과 1800초 HTTP timeout을 사용합니다.
처리량 제한과 dry-run payload만 Airflow 환경 변수로 조정합니다.

```text
DATA_MOVEMENT_LOAD_LIMIT=
DATA_MOVEMENT_LOAD_DRY_RUN=false
```

`airflow/dags/ct_process_comment_summary.py`는 별도 DAG `ct_process_comment_summary`로 아래 endpoint를 호출합니다.
요약은 `update_flag='Y'` row를 OpenWebUI로 처리하므로 파일 적재 DAG와 독립적으로 재시도하거나 중지할 수 있습니다.

```text
POST /api/v1/data-movement/ct_process_comment/summarize/
```

```text
DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_LIMIT=
DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_DRY_RUN=false
```

요약 DAG도 코드에 고정된 `*/1 * * * *` schedule과 1800초 HTTP timeout을 사용합니다.

송신 측에서 최종 파일명으로 직접 전송할 수 있으므로 API loader는 전송 중으로 보이는 파일을 적재 후보에서 제외합니다.
기본값은 마지막 수정 후 60초 이상 지난 파일만 후보로 보고, 1초 뒤 size/mtime이 그대로인 파일만 이번 실행에서 처리합니다.

```text
DATA_MOVEMENT_FILE_READY_MIN_AGE_SECONDS=60
DATA_MOVEMENT_FILE_READY_STABILITY_SECONDS=1
```

### Data Movement FTP

Compose의 `ftp` service는 API와 같은 host path를 공유합니다.
기본 host path는 `./data/data_movement`이며 API 컨테이너에서는 `/data/data_movement`로 보입니다.

```bash
make dev-infra-up
```

FTP 접속 기본값:

```text
host=<compose host>
port=6380
user=ftpuser
password=ftp1234
passive ports=8076-8079
```

운영/공유 환경에서는 아래 값을 env로 반드시 바꿉니다.

```text
FTP_USER
FTP_PASS
FTP_PASV_ADDRESS
FTP_PASV_MIN_PORT
FTP_PASV_MAX_PORT
DATA_MOVEMENT_HOST_PATH
```

### Drone JSON/CSV target seed

`seed_drone_targets_from_file`은 JSON/CSV의 `department`, `line`, `user_sdwt_prod` 목록을 기준으로
Drone SOP/발송 이력/알림 설정을 초기화한 뒤 다시 생성합니다.

입력 샘플은 `docs/examples/drone_targets.sample.json`,
`docs/examples/drone_targets.sample.csv`,
`docs/examples/drone_targets.multi_mapping.sample.csv`에 있습니다.

```json
{
  "targets": [
    {
      "department": "ENGR",
      "line": "L1",
      "target_user_sdwt_prod": "ETCH_A",
      "recipient_user_sdwt_prod": "ETCH_A",
      "channels": {
        "jira": {
          "enabled": false,
          "template_key": "common",
          "jira_project_key": "DRONE"
        },
        "messenger": {
          "enabled": true,
          "template_key": "common",
          "chatroom_id": null,
          "force_new_chatroom": true
        },
        "mail": {
          "enabled": true,
          "template_key": "common"
        }
      },
      "mappings": [
        {
          "sdwt_prod": "ETCH_A",
          "user_sdwt_prod": "ETCH_A"
        }
      ],
      "needtosend_rule": {
        "enabled": false,
        "comment_keyword": "$SETUP_EQP",
        "ignore_sample_type": false
      }
    }
  ]
}
```

주요 필드:

- `target_user_sdwt_prod`: `drone_sop_target.target_user_sdwt_prod`
- `recipient_user_sdwt_prod`: 수신인 자동 수집에 사용할 account 소속값
- `channels`: `drone_sop_target_channel_config` 생성값
- `mappings`: `drone_sop_target_mapping` 생성값
- `needtosend_rule`: `drone_sop_needtosend_rule` 생성값

사용 순서:

```bash
docker compose -f docker-compose.dev.yml exec -T api \
  python manage.py seed_drone_targets_from_file \
  --file /app/config/drone_targets.json \
  --dry-run

docker compose -f docker-compose.dev.yml exec -T api \
  python manage.py seed_drone_targets_from_file \
  --file /app/config/drone_targets.csv \
  --dry-run

docker compose -f docker-compose.dev.yml exec -T api \
  python manage.py seed_drone_targets_from_file \
  --file /app/config/drone_targets.json
```

초기화 범위:

- `drone_sop`
- `drone_sop_target_dispatch`
- `drone_sop_delivery`
- `drone_sop_target`
- `drone_sop_target_mapping`
- `drone_sop_target_channel_config`
- `drone_sop_needtosend_rule`
- `drone_sop_target_recipient`

CSV에서 하나의 target에 mapping이 여러 개인 경우 target row는 하나만 작성하고 `mappings`
컬럼에 JSON 배열을 넣습니다. 같은 `target_user_sdwt_prod`가 여러 행에 반복되면 command가
오류로 중단됩니다.

JSON/CSV 파일은 `api` 컨테이너가 읽을 수 있는 경로에 배치해야 합니다.
실제 실행 전에는 반드시 `--dry-run` 출력의 삭제/생성 카운트를 확인합니다.

## 환경 변수 파일

| 파일 | 역할 |
| --- | --- |
| `env/api.common.env` | API 공통 설정 |
| `env/api.dev.env` | API 개발 오버라이드 |
| `env/web.dev.env` | Web 개발 설정 |
| `env/minio.env` | MinIO 설정 |
| `env/grist.common.env` | Grist 공통 runtime 설정 |
| `env/grist.remote.env` | 새 Grist 서버 주소·port·Portal 검증 URL 설정 |
| `env/work-hub.oidc.env` | OIDC(stage) Portal의 원격 Grist 연결 설정 |
| `env/work-hub.prod.env` | 운영 Portal의 원격 Grist 연결 설정 |

## 주의할 점

- backend 테스트와 Django 명령은 `api` 컨테이너에서 실행합니다.
- 외부 연동 URL은 하드코딩하지 않고 env로 관리합니다.
- auth/RAG/assistant/mail 계약을 바꾸면 `apps/adfs_dummy`도 함께 갱신합니다.

## 문서 검증

문서가 실제 route/model/env inventory와 크게 어긋나지 않는지 확인합니다.

```bash
npm run agent:audit:docs
```

검증 대상:

- backend API prefix와 주요 endpoint
- frontend route와 feature facade
- 주요 Django model class
- management command
- env group

## 장애 확인 순서

| 증상 | 먼저 확인할 것 |
| --- | --- |
| 화면이 API를 못 부름 | `VITE_BACKEND_URL`, Nginx proxy, Django allowed hosts/CORS/CSRF |
| 로그인 redirect 실패 | `OIDC_REDIRECT_URI`, `ALLOWED_REDIRECT_HOSTS`, session cookie secure/samesite |
| Emails 수집 실패 | POP3 env, Airflow token, dummy mail endpoint 동작 |
| RAG/Assistant 실패 | `ASSISTANT_*`, `RAG_*`, dummy RAG endpoint, permission group |
| Drone 알림 실패 | SOP 수집 결과, target/channel/recipient 설정, Jira/Mail/Messenger env |
| Observer 조회 실패 | `OBSERVER_QUERY_DAYS`, data movement 적재 상태, 기준 정보 endpoint |
| 파일/이미지 실패 | MinIO env, bucket 접근, asset sequence |
