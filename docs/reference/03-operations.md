# 관리·검사 명령

[참고 자료](README.md) · [문서 홈](../README.md)

이 문서는 개발 검사와 Django 관리 명령의 실행 조건·옵션·데이터 변경을 설명합니다.
처음 실행은 [셋업 가이드](../getting-started/01-setup.md), 평소 시작·수정·검사·종료는 [자주 쓰는 명령](../getting-started/02-usage.md)을 먼저 확인합니다.
아래에서는 검사와 관리 명령의 상세 내용을 찾을 수 있습니다.

## 필요한 명령 찾기

| 작업 | 바로가기 |
| --- | --- |
| 로컬 앱·화면 실행 | [로컬 전체 앱](#로컬-전체-앱-실행), [프론트 명령](#프론트-명령) |
| API 테스트·관리 명령 | [백엔드 검증](#백엔드-검증), [Django 관리 명령](#django-관리-명령) |
| DB migration | [현재 적용 절차](../development/03-migration-guide.md) |
| 파일 적재·요약·FTP | [Data Movement](#data-movement-airflow-dag) |
| Drone 대상 초기 데이터 | [입력과 dry-run](#drone-jsoncsv-target-seed) |
| 설정·문서 검사·장애 대응 | [환경 변수](#환경-변수-파일), [문서 검증](#문서-검증), [장애 확인](#장애-확인-순서) |

## 실행 진입점

일반 작업에서는 저장소 루트의 `make` 명령을 사용합니다.
Kubernetes 정의는 `deploy/<app>`과 `local/<app>`에서 관리합니다. Compose는 로컬 DB·API 검사·CI에만 사용합니다.

| 환경 | 기본 명령 | 용도 | dependency source |
| --- | --- | --- | --- |
| `dev` | `make dev` | 로컬 개발 전용 | public registry/package source |
| `prod` | [운영 배포 안내](../../deploy/portal/k8s/overlays/prod/README.md) | 사내 Kubernetes | internal mirror |

`dev`는 로컬 PC에서만 사용하는 개발 환경입니다.
사내 서버는 Kubernetes만 사용합니다. Portal 입력은 `deploy/portal/env/prod`입니다.
`make down`은 로컬 kind 클러스터를 삭제하고 외부 DB 컨테이너를 종료하며 DB 볼륨과 호스트 데이터를 보존합니다.

## 로컬 전체 앱 실행

기동·상태 확인·종료 명령은 [일상 개발 안내](../getting-started/02-usage.md#시작확인종료)를 따릅니다.
한 PC의 kind에서 앱을 실행하고 PostgreSQL은 별도 Docker 컨테이너를 사용합니다.
주소·계정·설정·데이터 보존의 원본은 [로컬 실행 안내](../../local/README.md)입니다.

기동 도구는 DB·스토리지·Secret, 인증·mock, migration·seed, 앱과 후속 서비스를 준비합니다.
준비 상태 검사와 대표 기능 통합 검사는 확인하는 범위가 다르며, 통합 검사는 테스트 데이터를 만듭니다.
정상 종료는 DB 볼륨·호스트 파일·자격증명을 보존합니다. 포트·마운트 변경으로 클러스터 재생성이 필요하면
로컬 안내의 순서를 확인합니다.

## 사내 Kubernetes

`make server-check APP=all`은 local 파일 없이 모든 앱의 원본을 검사합니다.
서버는 registry·DNS/TLS·DB·스토리지·실제 외부계 입력을 별도로 준비합니다.
Portal migration은 운영 앱보다 먼저 실행하고, 여러 노드에서 FTP와 API 파일을 공유할 방식을 명시합니다.

배포 파일의 서비스별 역할은 [Kubernetes 배포 안내](../../deploy/README.md)를 참고합니다.
`make k8s-export`로 Keycloak 기동 YAML과 claim 등록 Job YAML을 각각 생성합니다.
claim 등록 Job은 Keycloak 기동과 사내 OIDC 설정을 완료한 뒤 별도로 실행합니다.

## 프론트 명령

[영역별 검사 표](../getting-started/02-usage.md#변경-영역별-검사)에서 Web 테스트·린트·빌드를 선택합니다.
UI 규칙이나 feature 공개면을 변경했다면 [검사 도구 안내](../../apps/tooling/README.md)의 해당 감사도 실행합니다.
Vite와 통합 환경의 API·로그인 연결 차이는 [Web 실행 안내](../../apps/portal/web/README.md#실행하기)를 따릅니다.

## 백엔드 검증

검사 image와 DB를 준비한 뒤 [API 실행 안내](../../apps/portal/api/README.md#실행하기)에 따라
설정·업무 테스트·migration 누락을 검사합니다. Django 명령은 일회성 Compose `api` 컨테이너에서 실행합니다.
`test-api`는 표준 test env와 별도 테스트 DB, 설정·migration 누락 검사는 합성된 로컬 env를 사용합니다.
소스 수정 뒤 검사 image를 갱신해야 변경한 코드가 검사됩니다.

## Django 관리 명령

전체 명령 이름·구현 파일·목적은 [관리 명령 색인](02-inventory.md#management-command)에서 찾습니다.
이곳에서는 실행 방법과 파일 입력·데이터 변경을 설명합니다.

### 로컬 관리 명령 실행 방법

먼저 [로컬 환경](../../local/README.md)을 준비하고, API 소스를 바꿨다면 검사 이미지를 갱신합니다.
아래 명령은 저장소 루트에서 도움말만 조회합니다.

```bash
docker compose --project-name tailwind-k8s-check --env-file local/shared/runtime/db.env \
  -f local/shared/compose/k8s-check.yml run --rm -T api help process_email_outbox
```

`help process_email_outbox`를 필요한 명령과 옵션으로 바꿉니다.
DB 쓰기·외부 발송·삭제 여부와 dry-run 지원은 해당 명령의 도움말을 확인합니다.
파일 입력은 컨테이너에서도 읽을 수 있어야 하며, [Drone 예시](#drone-jsoncsv-target-seed)처럼 읽기 전용 마운트를 사용합니다.

### 개발용 초기 데이터와 로그인 권한

로컬 기동 도구는 별도 `portal-seed` Job으로 `seed_dev_data`를 실행하며 `--reset`을 사용하지 않습니다.
`seed_dev_data`는 `ENVIRONMENT=development`에서 동작합니다. 초기 데이터를 다시 만들 때는 명령을 명시적으로 실행합니다.
로그인 권한은 Keycloak 역할·그룹에서 가져오며 Django 관리자 플래그와 별도로 검사합니다.

### DB migration

현재 배포 이미지·API Secret을 사용한 사전 검사·API 중지·migration·사후 확인은
[migration 적용 안내](../development/03-migration-guide.md)를 따릅니다.

### Assistant 데이터 보강 명령

`backfill_assistant_run_access`는 저장된 메시지·요약·제목의 Profile과 접근 요구사항을 보강합니다.
도움말과 dry-run 결과를 확인한 뒤 필요한 데이터에만 실행합니다. checkpoint를 사용해 중단·재개할 수 있습니다.
권한을 분류할 수 없는 데이터는 `legacy-unresolved`로 두며, 이 명령으로 로그인 권한을 부여하지 않습니다.

## Data Movement Airflow DAG

`apps/airflow/dags/data_movement_file_load.py`는 기본 1분 주기로 아래 파일 적재 endpoint를 호출합니다.

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
테이블별 파일 패턴·DB 반영 방식·원천 시각 해석은 [Data Movement 적재 규칙](../modules/13-data-movement.md#테이블별-적재-규칙)을 따릅니다.
파일 적재 DAG는 코드에 고정된 `*/1 * * * *` schedule과 1800초 HTTP timeout을 사용합니다.
처리량 제한과 dry-run payload만 Airflow 환경 변수로 조정합니다.

```text
DATA_MOVEMENT_LOAD_LIMIT=
DATA_MOVEMENT_LOAD_DRY_RUN=false
```

`apps/airflow/dags/ct_process_comment_summary.py`는 별도 DAG `ct_process_comment_summary`로 아래 endpoint를 호출합니다.
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

FTP와 API는 같은 호스트 데이터 폴더를 공유합니다. 파일 전달 규칙은 [Data Movement](../modules/13-data-movement.md#주의사항),
접속 주소·계정은 [로컬 안내](../../local/README.md#주소와-계정), 서버 입력은 [FTP 배포](../../deploy/ftp/README.md)를 따릅니다.

## Drone JSON/CSV target seed

`seed_drone_targets_from_file`은 JSON/CSV의 `department`, `line`,
`target_user_sdwt_prod`, `recipient_user_sdwt_prod` 목록을 기준으로 Drone SOP/발송
이력/알림 설정을 초기화한 뒤 다시 생성합니다. 구형 top-level `user_sdwt_prod`
별칭은 허용하지 않습니다.

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

### 입력 파일 연결과 미리 보기

아래 예시는 저장소의 샘플 폴더를 읽기 전용으로 연결하고 JSON 입력을 **dry-run으로만 검사**합니다.
실제 사용 전 샘플을 기준으로 대상 정보를 준비하고 호스트 경로·파일 이름을 그 파일에 맞게 바꿉니다.

```bash
docker compose --project-name tailwind-k8s-check --env-file local/shared/runtime/db.env \
  -f local/shared/compose/k8s-check.yml run --rm -T \
  -v "$PWD/docs/examples:/app/config:ro" api \
  seed_drone_targets_from_file --file /app/config/drone_targets.sample.json --dry-run
```

CSV를 검사하려면 파일 이름을 `drone_targets.sample.csv`로 바꿉니다.
삭제·생성 카운트와 대상 DB를 확인한 뒤 실제 적용할 때만 같은 명령에서 `--dry-run`을 제거합니다.

### 초기화 범위

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

설정 파일별 역할·설정 그룹·적용 순서는 [환경 설정](01-configuration.md)에 있습니다.
서버의 실제 입력·Secret 등록은 [앱별 환경설정](../../deploy/shared/docs/configuration/environment.md)을 따릅니다.
각 앱은 자신의 env를 사용하며 로컬 API는 기본 env·Kubernetes 차이·생성된 override를 합성합니다.

## 주의할 점

- backend 테스트와 Django 명령은 `api` 컨테이너에서 실행합니다.
- 외부 연동 URL은 하드코딩하지 않고 env로 관리합니다.
- auth/RAG/assistant/mail 계약을 바꾸면 `local/adfs_dummy`도 함께 갱신합니다.

## 문서 검증

문서가 실제 route/model/env inventory와 크게 어긋나지 않는지 확인합니다.

```bash
make audit-docs
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
| RAG/Assistant 실패 | `OPENWEBUI_*`, `ASSISTANT_*`, `RAG_*`, mock 응답, permission group |
| Drone 알림 실패 | SOP 수집 결과, target/channel/recipient 설정, Jira/Mail/Messenger env |
| Observer 조회 실패 | `OBSERVER_QUERY_DAYS`, data movement 적재 상태, 기준 정보 endpoint |
| 파일/이미지 실패 | MinIO env, bucket 접근, asset sequence |

사내 서버는 [선택 체크아웃](../../deploy/01-SERVER_CHECKOUT.md) 후 `make server-check APP=<앱>`을 사용합니다. 전체 env·로컬 렌더링 검사는 개발 PC에서 수행합니다.
