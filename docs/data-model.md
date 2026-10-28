# 데이터 모델과 저장소

이 앱은 기본 업무 DB, MinIO, 외부 시스템을 함께 사용합니다.

## 저장소 개요

| 저장소 | 설정 | 사용 모듈 | 역할 |
| --- | --- | --- | --- |
| 기본 PostgreSQL | `DJANGO_DB_*` | Account, Emails, Drone, AppStore, VOC, Activity, Assistant, Data Movement, L3 | 업무 데이터, 앱 카탈로그, 이력·로그·알림 상태 |
| MinIO | `MINIO_*` | Emails/Common | 메일 asset 파일 저장/조회 |
| Dummy 외부계 memory/file | `local/adfs_dummy` | 로컬 Auth/RAG/LLM/Mail/Jira | 외부 시스템 대체 |
| 외부 RAG/LLM/Mail/Jira/Messenger | env 기반 URL/token | Emails, Assistant, Drone | 검색, 답변, 알림, 메일 전송 |

## 기본 DB 모델

| App | 모델 | 목적 |
| --- | --- | --- |
| Account | `User` | 로그인 사용자와 OIDC claim 기반 사용자 정보 |
| Account | `Affiliation` | line, SDWT, product 기준 소속 단위 |
| Account | `UserCurrentAffiliation` | 사용자의 현재 소속 |
| Account | `UserSdwtProdAccess` | 접근 가능한 SDWT/product 권한 |
| Account | `UserSdwtProdChange` | 소속/권한 변경 요청과 승인 상태 |
| Account | `ExternalAffiliationSnapshot` | 외부 예측 소속 snapshot |
| Account | `AccessScope` | Portal·앱·기능 접근 권한 범위 |
| Account | `AccessPolicyRule` | scope별 부서 자동 접근 정책 |
| Account | `UserAccess` | 사용자별 scope 접근 상태와 고정 역할 |
| Account | `UserScopeAffiliationGrant` | 기존 사용자·앱별 소속 grant 이력 |
| Account | `AccessRole`, `AccessSource` | 기존 DB 권한 역할·출처 기준 |
| Account | `AccessAuditLog` | 접근 상태·정책·scope 변경 감사 이력 |
| Activity | `ActivityLog` | 사용자/시스템 활동 로그 |
| Activity | `ExternalAppAccessDailyStat`, `ExternalAppUsageSyncState` | 외부 접속 통계와 마지막 동기화·제한 상태 |
| Assistant | `AssistantConversation` | 사용자별 UUID 대화방, 현재 분기, 고정·보관 상태 |
| Assistant | `AssistantConversationSummary` | 기억 partition별 요약과 접근 요구사항 |
| Assistant | `AssistantMessage` | 대화방별 user/assistant 메시지, context, 출처, parent·revision 관계 |
| Assistant | `AssistantGeneration` | 사용자 단위 활성 생성 lease와 종료 상태 |
| Assistant | `AssistantContextSnapshot` | 업무 화면 분석 범위·coverage·제한된 근거 snapshot |
| Assistant | `AssistantMessageFeedback` | Assistant 답변별 사용자 평가 |
| Data Movement | `MInterlock` | m_interlock 원천 파일의 interlock_no 기준 최신 이력 |
| Data Movement | `MInterlockLoadJob` | m_interlock 파일별 적재 상태와 처리 결과 |
| Emails | `Email` | 수집/작성/분류된 메일 본문과 metadata |
| Emails | `EmailOutbox` | RAG insert/delete 비동기 작업 |
| Emails | `EmailAsset` | 메일 첨부/이미지/OCR 대상 asset metadata |
| Drone | `DroneSOP` | SOP 이벤트 본문과 기준 상태 |
| Drone | `DroneSopTarget` | 알림 대상 line/소속 단위 |
| Drone | `DroneSopTargetChannelConfig` | target별 channel 설정 |
| Drone | `DroneSopNeedToSendRule` | 전송 필요 여부 rule |
| Drone | `DroneSopTargetMapping` | SOP와 target 매핑 |
| Drone | `DroneSopTargetRecipient` | target별 수신자 |
| Drone | `DroneSopTargetDispatch` | target dispatch 실행 단위 |
| Drone | `DroneSopDelivery` | channel별 전송 결과 |
| Drone | `DroneEarlyInform` | 조기 알림/라인 대시보드 데이터 |
| AppStore | `AppStoreApp` | 내부 앱 등록 정보 |
| AppStore | `AppStoreLike` | 앱 좋아요 |
| AppStore | `AppStoreComment` | 앱 댓글 |
| AppStore | `AppStoreCommentLike` | 댓글 좋아요 |
| VOC | `VocPost` | VOC 게시글 |
| VOC | `VocReply` | VOC 답변 |
| L3 Spider | `L3SpiderFileIndex`, `L3SpiderDailyRunStats`, `L3SpiderRunStatus` | 파일 인덱스·일별 통계·실행 상태 |
| L3 Spider | `L3SpiderLineNameRule`, `L3SpiderExclusionFilter` | 라인 이름 매핑·제외 조건 |
| L3 Spider | `L3SpiderMailRule`, `L3SpiderMailDelivery`, `L3SpiderMailRulePermission` | 메일 예약·발송 이력·공유 권한 |

## 모델이 없는 app

| App | 데이터 위치 |
| --- | --- |
| `api.auth` | `api.account.User`와 session/OIDC claim 사용 |
| `api.rag` | 외부 RAG API client |
| `api.observer` | 기본 DB의 data movement/업무 테이블 read-only 조회 |
| `api.l0_spider`, `api.pm_comparison`, `api.tttm_spider` | read-only 마운트된 Parquet·참조 파일 |
| `api.health` | 프로세스 상태 payload |
| `api.common` | 공통 service/helper |

Account의 소속·권한 테이블은 기존 데이터와 migration 이력으로 남아 있습니다. 현재 로그인 권한은
Keycloak 세션의 앱 역할·SDWT 그룹으로 판정하며 `UserAccess`, `UserSdwtProdAccess`와
Django 관리자 플래그를 권한 원천으로 사용하지 않습니다.

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
- `MInterlock`은 원천 필드와 함께 `prod_eqp_id_lookup`, `interlock_kind_lookup`, `prod_progs_at`을 dual-write하며, Observer는 typed keyset 인덱스 `idx_m_intlk_obs_page`를 활용할 수 있는 조건으로 조회합니다. 실제 실행 계획은 DB 통계와 조회 조건에 따라 달라집니다. 기존 문자열 조회 표현식 인덱스는 제거합니다. typed 파생 필드가 비어 있는 기존 row는 Observer 조회에서 제외하며 별도 호환 경로를 제공하지 않습니다.

## 변경 시 확인 항목

- migration이 필요한 기본 DB schema 변경인지 확인합니다.
- 모델 추가/삭제/필드 변경 시 `docs/data-model.md`, 해당 모듈 문서, API response 문서를 함께 갱신합니다.
- 파일 저장 정책 변경 시 `docs/integrations.md`의 MinIO와 `docs/configuration.md`의 `MINIO_*`를 갱신합니다.
