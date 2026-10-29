# Data Movement 모듈

[모듈 목록](README.md) · [문서 홈](../README.md) · [API 호출 계약](../api/14-data-movement.md)

Data Movement는 FTP 등으로 받은 압축 CSV 파일을 읽어 PostgreSQL 업무 테이블에 반영합니다.
화면에서 직접 입력하는 기능이 아니라, 수동 관리 명령·Airflow 작업·내부 API로 실행하는 데이터 준비 기능입니다.
적재한 기준정보와 로그는 Observer 등 다른 업무 기능에서 조회합니다.

파일은 **전송 완료 → incoming 대기 → processing 처리 → DB 반영 → 처리 파일 삭제** 순서로 이동합니다.
테이블마다 전체 교체와 증분 갱신 방식이 다르므로 아래 적재 규칙을 확인합니다.

## 디렉터리

테이블별 데이터 루트 아래 `incoming/`에 전송을 마친 파일을 둡니다. 적재기는 파일을 `processing/`으로 원자적으로 이동해 처리 대상을 확보하고, 성공·실패 후 처리 파일을 삭제합니다.
로컬 Kubernetes 기본 host path는 `./data/data_movement`이고, API 컨테이너에서는 `/data/data_movement`로 mount됩니다.

| 테이블 | 기본 root | 파일 패턴 |
| --- | --- | --- |
| `m_tkin_prevent` | `/data/data_movement/m_tkin_prevent` | `*.csv.deflate` |
| `ctttm_workorder_list` | `/data/data_movement/ctttm_workorder_list` | `*CT_*_WORKORDER_*.csv.deflate` |
| `ct_process_comment` | `/data/data_movement/ct_process_comment` | `*_CT_PROCESS_COMMENT_*.csv.deflate` |
| `eqp_status_chg` | `/data/data_movement/m_eqp_status_chg` | `*m_eqp_status_chg*.csv.deflate` |
| `m_interlock` | `/data/data_movement/m_interlock` | `m_interlock_*_????????_????.csv.deflate` |
| `mi_tip_update_hist` | `/data/data_movement/mi_tip_update_hist` | `*mi_tip_update_hist*.csv.deflate` |
| `racb_list` | `/data/data_movement/racb_list` | `*racb_list*.csv.deflate` |
| `mes_line_mapping_info` | `/data/data_movement/mes_line_mapping_info` | `*_MES_LINE_MAPPING_INFO_*.csv.deflate` |
| `station_master` | `/data/data_movement/station_master` | `*_STATION_MASTER_*.csv.deflate` |

### 테이블별 적재 규칙

`ctttm_workorder_list`는 `CT_MST_WORKORDER`와 `CT_MNU_WORKORDER`의 원천 컬럼 수와 순서가 다릅니다.
loader는 파일명에서 source를 추출한 뒤 MST는 55개 컬럼, MNU는 49개 컬럼 레이아웃으로 백틱(`) 구분 파일을 읽습니다.

`mes_line_mapping_info`는 파일 하나가 테이블 전체 snapshot이므로 새 파일 처리 시 기존 row를 모두 삭제하고 파일 전체를 다시 적재합니다.

`station_master`도 파일 하나를 테이블 전체 snapshot으로 보고 전체 교체 적재합니다.

`eqp_status_chg`는 `eqp_event_key` 기준으로 증분 upsert하고, `eqp_id`가 `E/e`로 시작하지 않거나 `chg_time`이 180일보다 오래된 row를 제외합니다. 저장 시 `eqp_cb=eqp_id-chamber_id`를 생성하며, 적재 후 target의 180일 초과 row도 삭제합니다. 원천 `chg_time`, `last_update_time`은 timezone 없는 KST 벽시계 값으로 해석합니다. 원천 파일 retention 경계는 KST 벽시계, DB purge 경계는 같은 순간의 UTC를 사용합니다.

`m_interlock`은 `m_interlock_<LineID>_<YYYYMMDD>_<HHMM>.csv.deflate` 파일의 헤더 없는 35개 백틱(`) 구분 컬럼을 `interlock_no` 기준으로 upsert합니다. 빈 `interlock_no` row는 제외하고 파일 내 중복은 마지막 row를 사용합니다. 기존 DB 중복은 `last_update_date` 최신순, 이후 `id` 내림차순으로 한 건만 유지합니다. numeric 컬럼은 PostgreSQL 무제한 `numeric` precision을 유지하고 `lot_id`는 길이 제한 없는 `text`로 저장하며 retention은 적용하지 않습니다.

`mi_tip_update_hist`는 TIP 원천 이력을 `tip_event_key` 기준으로 upsert하고, 원천 타입 조합을 timeline event type으로 매핑합니다. 원천 `rule_pkg_update_date`, `gpm_update_date`, `last_update_date`는 timezone 없는 KST 벽시계 값으로 해석합니다.

`racb_list`는 `c_racb_id`별 최신 `update_date` row를 고른 뒤 `eqp_ids`를 comma split하여 `eqp_cb` row로 펼쳐 저장합니다.

### EQP·TIP 시간 해석

EQP/TIP의 시간대 없는 원천 값은 KST 벽시계로 해석하고, DB에는 그 순간에 해당하는 시각을 저장합니다.
Observer 화면의 Data Log와 Log Detail은 같은 KST 시각으로 표시합니다.
DB schema·데이터 변환은 저장소의 migration으로 관리하며 파일 적재 단계에서 임의로 9시간을 다시 더하거나 빼지 않습니다.

## 실행 방식

- 수동 실행: Django management command
- 자동 실행: Airflow DAG `data_movement_file_load`
- CTTTM comment 요약 자동 실행: Airflow DAG `ct_process_comment_summary`
- 내부 API: `POST /api/v1/data-movement/<table_name>/load/`
- CTTTM comment 요약 API: `POST /api/v1/data-movement/ct_process_comment/summarize/`
- 파일 수신: Kubernetes FTP DaemonSet

## Airflow 순서

`ct_process_comment`는 `ctttm_workorder_list`의 workorder 목록을 기준으로 적재 대상을 필터링합니다.
따라서 DAG는 `ctttm_workorder_list` 성공 후 `ct_process_comment`를 실행합니다.
`ct_process_comment` 요약은 별도 `ct_process_comment_summary` DAG에서 실행되며, `update_flag='Y'` row를 최근 업데이트 순으로 처리합니다.
`m_tkin_prevent`, `eqp_status_chg`, `m_interlock`, `mi_tip_update_hist`, `racb_list`, `mes_line_mapping_info`, `station_master`는 독립적으로 실행됩니다.

## 주의사항

업로드는 임시 파일명으로 전송한 뒤 완료 시 `incoming/`의 최종 파일명으로 바꾸는 방식을 사용합니다.
최종 파일명으로 전송되는 경우에도 적재기는 수정 후 대기 시간과 size/mtime 안정성을 확인해 처리 후보를 고릅니다.
기본값과 조정 가능한 env는 [적재 실행 조건](../reference/03-operations.md#data-movement-airflow-dag)에 있습니다.

## FTP

FTP 배포와 이미지·계정 입력은 [FTP 안내](../../deploy/ftp/README.md)를 따릅니다.
FTP에서 보이는 `data_movement` 디렉터리는 API의 `/data/data_movement`와 같은 host path입니다.

기본 접속 설정은 env로 바꿀 수 있습니다.

```text
FTP_USER=ftpuser
FTP_PASS=<생성된 로컬 credential 또는 운영 Secret>
FTP_PORT=6380
FTP_PASV_ADDRESS=127.0.0.1
FTP_PASV_MIN_PORT=8076
FTP_PASV_MAX_PORT=8079
DATA_MOVEMENT_HOST_PATH=./data/data_movement
```

운영에서는 `FTP_PASS`와 `FTP_PASV_ADDRESS`를 반드시 배포 환경에 맞게 설정합니다.
