# 데이터 모델과 저장소

[문서 홈](../README.md) · [첫 셋업](../getting-started/01-setup.md) · [자주 쓰는 명령](../getting-started/02-usage.md)

업무 데이터와 처리 이력은 PostgreSQL에, 메일 첨부·이미지는 MinIO에 저장합니다.
일부 분석 화면은 컨테이너에 읽기 전용으로 연결한 Parquet 참고 파일을 조회합니다.
로컬 mock의 RAG·메일 샌드박스는 메모리 저장소이므로 업무 DB·파일과 보존 방식이 다릅니다.

아래에서는 먼저 저장 위치와 데이터 관계를 설명하고, 뒤에서 실제 모델 이름을 찾을 수 있습니다.
로컬 종료·재기동 시 보존되는 파일과 백업 대상은 [로컬 데이터 보존 안내](../../local/README.md#로컬-설정과-파일-보존)를 확인합니다.

## 저장소 개요

| 저장소 | 설정 | 사용 모듈 | 역할 |
| --- | --- | --- | --- |
| 기본 PostgreSQL | `DJANGO_DB_*` | Account, Emails, Drone, AppStore, VOC, Activity, Assistant, Data Movement, L3 | 업무 데이터, 앱 카탈로그, 이력·로그·알림 상태 |
| MinIO | `MINIO_*` | Emails/Common | 메일 asset 파일 저장/조회 |
| Dummy 외부계 memory/file | `local/adfs_dummy` | 로컬 Auth/RAG/LLM/Mail/Jira | 외부 시스템 대체 |
| 외부 RAG/LLM/Mail/Jira/Messenger | env 기반 URL/token | Emails, Assistant, Drone | 검색, 답변, 알림, 메일 전송 |

## 주요 관계

- `User`의 EPID와 검증된 로그인 세션을 연결하고, 세션의 SDWT 등급으로 업무 데이터 접근 범위를 판정합니다.
- `AssistantConversation`은 `User`에 속하고 `current_message`에서 parent를 따라 현재 분기를 결정하며 `pinned_at`, `archived_at`을 보관합니다. `AssistantConversationSummary`는 `(conversation, context_key)`별 rolling summary와 포함 메시지 위치를 보관합니다.
- `AssistantMessage`는 대화방 삭제 시 cascade 삭제되며 `(conversation, client_id)` constraint가 메시지 저장 재시도를 멱등 처리합니다. `parent`, `revision_of`로 질문 편집과 답변 재생성 전 원본 분기를 보존합니다.
- `AssistantGeneration`은 queued/streaming 상태에 대한 사용자 partial unique constraint와 `(user, client_request_id)` 멱등 constraint를 사용합니다. `AssistantContextSnapshot`은 원본 대량 행 대신 제한된 JSON과 hash를 저장하고, `AssistantMessageFeedback`은 메시지 one-to-one 평가입니다.
- Emails는 mailbox/소속 접근 범위를 기준으로 메일 목록과 상세 접근을 제한합니다.
- `EmailOutbox`는 RAG 등록/삭제 작업을 보관하고 `process_email_outbox`가 처리합니다.
- Drone SOP는 target, channel config, recipient, dispatch, delivery로 분리되어 알림 설정과 발송 결과를 추적합니다.
- AppStore와 VOC는 작성자와 댓글/답변 관계를 기본 DB에 저장합니다.
- Observer는 기준정보를 기본 DB의 `drone_sop_target`, `station_master`에서 조회하고, 로그를 `eqp_status_chg`, `mi_tip_update_hist`, `m_interlock`, `ctttm_workorder_list`, `ct_process_comment`, `racb_list`, `drone_sop`에서 조회합니다.
- `MInterlock`은 원천 필드와 함께 `prod_eqp_id_lookup`, `interlock_kind_lookup`, `prod_progs_at`을 dual-write하며, Observer는 typed keyset 인덱스 `idx_m_intlk_obs_page`를 활용할 수 있는 조건으로 조회합니다. 실제 실행 계획은 DB 통계와 조회 조건에 따라 달라집니다. typed 파생 필드가 비어 있는 행은 Observer 조회에서 제외합니다.

## 기본 DB 모델

전체 모델 이름은 [DB 모델 색인](../reference/02-inventory.md#주요-db-모델)에서 관리합니다.
여기서는 저장하는 정보와 다른 기능과의 관계를 설명합니다.

| 데이터 영역 | 저장하는 정보 | 연결되는 기능 |
| --- | --- | --- |
| Account | 사용자 신원·활성 앱 카탈로그·소속과 접근 데이터 | 로그인 세션·앱 접근 검사 |
| Activity | 사용자 작업·앱 접속 집계·외부 사용량 동기화 상태 | 접속 통계 화면·활동 로그 |
| Assistant | 대화방·메시지 분기·생성 상태·기억·근거·평가 | 전체 대화·화면별 ChatWidget |
| Emails | 메일·첨부 metadata·검색 등록/삭제 작업 | 메일함·OCR·MinIO·RAG |
| Drone | SOP·알림 대상·채널·수신자·실행·전달 결과 | Line Dashboard·메일/Jira/Messenger |
| Data Movement | 9종 원천 테이블과 테이블별 적재 작업 상태 | Observer 기준정보·로그·예방 상태·요약 |
| AppStore | 앱·댓글·좋아요·노출 순서 | 내부 앱 공유 |
| VOC | 문의·개선 요청·답변 | VOC 게시판 |
| L3 Spider | 파일 인덱스·일별 실행 상태·라인 규칙·제외 조건·메일 규칙/결과 | 이상감지·예약 메일 |

Data Movement는 `m_tkin_prevent`, `ctttm_workorder_list`, `ct_process_comment`, `eqp_status_chg`,
`m_interlock`, `mi_tip_update_hist`, `racb_list`, `mes_line_mapping_info`, `station_master`를 적재합니다.
전체 교체·증분 갱신·기간 제한은 [테이블별 적재 규칙](../modules/13-data-movement.md#테이블별-적재-규칙)에 있습니다.

## 모델이 없는 app

| App | 데이터 위치 |
| --- | --- |
| `api.auth` | `api.account.User`와 session/OIDC claim 사용 |
| `api.rag` | 외부 RAG API client |
| `api.observer` | 기본 DB의 data movement/업무 테이블 read-only 조회 |
| `api.l0_spider`, `api.pm_comparison`, `api.tttm_spider` | read-only 마운트된 Parquet·참조 파일 |
| `api.health` | 프로세스 상태 payload |
| `api.common` | 공통 service/helper |

현재 Account schema에는 소속·권한 모델도 정의되어 있습니다. 로그인 권한은 Keycloak 세션의
앱 역할·SDWT 그룹으로 판정하며, `UserAccess`·`UserSdwtProdAccess`나 Django 관리자 플래그를 권한 원천으로 사용하지 않습니다.

## 변경 시 확인 항목

- migration이 필요한 기본 DB schema 변경인지 확인합니다.
- 모델 추가/삭제/필드 변경 시 `docs/concepts/02-data-model.md`, 해당 모듈 문서, API response 문서를 함께 갱신합니다.
- 파일 저장 정책 변경 시 `docs/concepts/03-integrations.md`의 MinIO와 `docs/reference/01-configuration.md`의 `MINIO_*`를 갱신합니다.
