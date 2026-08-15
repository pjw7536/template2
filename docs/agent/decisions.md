# Agent Decisions

이 문서는 반복 설명 비용을 줄이기 위한 확정 결정만 기록한다.

## 확정된 운영 결정
- 프로젝트 전용 skill은 `.codex/skills/*/SKILL.md`에 둔다.
- `.codex/skills/.system/**`은 로컬 시스템 skill로 보고 추적/공유 대상에서 제외한다.
- frontend UI 변경 후에는 `npm run agent:audit:ui` 또는 `scripts/agent/check_ui_consistency.sh`를 실행한다.
- frontend feature import/export/routing 변경 후에는 `npm run agent:audit:web-boundary` 또는 `scripts/agent/check_frontend_boundaries.sh`를 실행한다.
- backend domain boundary/import/view/selector 변경 후에는 `npm run agent:audit:api-boundary` 또는 `scripts/agent/check_backend_boundaries.py`를 실행한다.
- PR에서는 `.github/workflows/feature-guardrails.yml`의 frontend boundary, backend boundary, lint, build, backend syntax 검사를 통과해야 한다.
- AI가 feature 작업을 수행할 때는 `docs/agent/ai-feature-workflow.md`의 기본 프롬프트와 검증 절차를 따른다.
- 큰 작업은 `docs/agent/PLANS.md`의 ExecPlan 기준을 따른다.
- eval은 `docs/agent/evals/*`의 작업/성공 기준을 기준으로 누적한다.
- OIDC 개발과 운영 Compose의 외부 registry image는 `repository.samsungds.net`를 사용하고, 외부 dev Compose는 public image 이름을 유지한다.

## 보류된 결정
- multi-agent orchestration은 eval에서 병렬 검토 효과가 확인될 때까지 도입하지 않는다.

## 2026-06-19: backend boundary audit 1차 도입

- backend boundary audit은 `scripts/agent/check_backend_boundaries.py`의 AST 기반 검증으로 운영한다.
- 1차 실패 기준은 cross-domain internal import, test cross-domain internal import, `views.py` 직접 ORM, `selectors.py` write ORM, backend app 구조 위반이다.
- 기존 service direct read ORM 후보는 범위가 넓어 CI 실패 기준에 넣지 않고 별도 debt로 관리한다.
- CI backend job은 boundary audit 후 Python compile을 실행한다.

## 2026-05-17: 앱 문서 상세화 구조

- 문서 홈은 `docs/README.md`로 유지하고, 실제 route/model/env/command 색인은 `docs/inventory.md`로 분리한다.
- 주제별 상세 문서는 `docs/backend.md`, `docs/frontend.md`, `docs/data-model.md`, `docs/configuration.md`로 분리해 문서가 길어져도 읽기 흐름을 유지한다.
- 모듈 문서는 업무 흐름과 운영 포인트를 담당하고, API 문서는 endpoint 계약을 담당한다.
- 문서 drift를 줄이기 위해 `scripts/agent/check_docs_inventory.sh`로 backend endpoint, frontend route, model, command, env group의 문서 반영 여부를 검증한다.

## 2026-05-29: data_movement 테이블별 중첩 앱 구조

- 파일 기반 DB 적재 기능은 `apps/api/api/data_movement/<table_name>` 아래에 테이블별 Django app으로 둔다.
- `<table_name>` 폴더명은 실제 target table 이름과 일치시킨다.
- 테이블별 app은 자기 model, migration, loader service, tests, management command만 소유한다.
- 공통 파일 탐색, deflate CSV 파싱, PostgreSQL COPY 유틸은 `apps/api/api/data_movement/common`에 둔다.

## 2026-07-27: Portal·앱 고정 역할 접근 권한

- Portal과 모든 하위 scope의 역할은 `UserAccess.role`의 `user`/`admin` 두 값으로 통일한다.
- canonical `portal` key 이외의 모든 scope는 Portal 접근을 선행 조건으로 사용한다.
- 자동 정책과 일괄 승인은 `user`만 부여하고 `admin`은 사용자별 명시 권한으로만 부여한다.
- `pending`·`denied` 행은 `user`만 저장하며, 역할 없는 승인·부여도 기존 역할 대신 `user`를 사용한다.
- Portal `admin`은 전역 접근 관리, 앱 `admin`은 해당 앱의 관리자 기능만 담당한다.
- 역할 판정은 요청 단위 일괄 resolver를 사용하고 전역 캐시는 사용하지 않는다.
- 별도 소비처가 없는 사용자 프로필 운영 역할은 제거하고 권한 역할은 `UserAccess.role`만 사용한다.
- 인증 응답의 접근 정보는 Portal과 모든 활성 scope를 포함한 `scope_access` 하나만 사용한다.
- 접근 신청은 `/account/access/request`, 관리 결정은 `/account/access/users/<user_id>/decision`만 사용한다.
- 접근 관리 요청 body와 query는 camelCase canonical 필드만 허용하고 이전 별칭은 400으로 거절한다.
- 접근 차단 오류는 scope 종류와 관계없이 `scope_access_required`, `scope`, `access` 형태를 사용한다.
- 제거된 `portal_access`, `app_access`, Portal 전용 승인 API, 정책 가상 역할, `canManage` 호환 계층은 복구하지 않는다.
- `AccessScope`는 migration으로만 추가하고 `key`·유형을 변경하거나 행을 물리 삭제하지 않는다.
- canonical Portal은 `key=portal`과 `scope_type=portal`을 DB 제약조건으로 함께 고정한다.
- 권한 매트릭스는 Portal과 모든 활성 app·feature scope를 같은 결정 API로 관리한다.
- 사용자와 scope는 비활성화로 수명을 관리하고 감사 로그가 참조하는 행은 `PROTECT`한다.

## 2026-07-29: 소속 역할과 앱별 데이터 범위

- 소속 역할 capability는 `viewer=조회`, `member=조회·일반 변경`, `manager=조회·일반 변경·삭제·소속 승인·권한 관리`로 고정한다.
- 소속 변경 승인·거절은 대상 소속 manager만 가능하며 요청자는 자신의 요청을 처리할 수 없다.
- 마지막 manager는 강등하거나 회수할 수 없고, 현재 소속 접근 자체도 회수하지 않는다.
- 앱 접근, 앱별 소속 데이터 범위, 소속 역할 capability는 서로 독립적으로 판정한다.
- Emails 이동은 source와 target 모두 member 이상, 삭제는 대상 소속 manager를 요구한다.
- Emails 전역 운영 특권은 Emails `admin` 역할과 `data_scope_mode=all`을 모두 가진 경우에만 활성화한다.

## 2026-07-30: 소속 권한 동시성·감사 불변조건

- 사용자별 `PENDING` 소속 변경 요청은 DB 조건부 unique constraint로 한 건만 허용한다.
- 소속 변경 승인·거절과 소속 역할 관리는 대상 `Affiliation` 잠금을 공통 직렬화 지점으로 사용하고 잠금 뒤 최신 manager 역할을 재검사한다.
- 소속 역할 부여·변경·회수와 `data_scope_mode`의 실질적 변경은 원본 권한 변경과 같은 transaction에서 `AccessAuditLog`로 기록한다.
- 비활성 `Affiliation`은 현재 소속·소속 역할·앱별 grant 계산에서 모두 제외하며,
  연결 설정은 삭제하지 않고 전역 일시중지 상태로 보존한다.
- 여러 `Affiliation`을 잠그는 쓰기 경로는 항상 `Affiliation.id` 오름차순을 사용한다.
- Django Admin은 현재 소속과 소속 변경 요청을 직접 저장하지 않고 서비스 action만 사용한다.
- 소속 기준정보의 생성·자동 동기화 변경·활성 상태 변경은 모두 같은 transaction에서 lifecycle 감사 로그를 남긴다.
- Admin 소속 일괄 활성 상태 변경은 운영자 사유를 필수로 받고 선택 행 전체를 하나의 transaction으로 처리한다.
- `UserSdwtProdChange`는 상태별 승인 시각·승인자·거절 사유 조합까지 DB CheckConstraint로 강제한다.
- 여러 소속의 capability 판정은 활성 소속과 명시 역할을 일괄 조회하고 현재 소속의 암묵적 member 규칙을 합산한다.

## 2026-07-31: Observer 표시·조회 시간대

- Observer의 날짜-only 및 offset 없는 조회 query는 `Asia/Seoul` 현지 시각으로 해석한다.
- offset이 있는 조회 query와 DB aware datetime은 같은 instant의 `Asia/Seoul` 시각으로 변환한다.
- Observer API의 공통 시간 필드는 `+09:00` offset을 포함한 ISO datetime으로 반환한다.
- Timeline 축, Data Log, Log Detail, 날짜 범위 계산은 브라우저 지역과 관계없이 `Asia/Seoul`을 사용한다.
- EQP의 `chg_time`, `last_update_time`과 TIP의 `rule_pkg_update_date`, `gpm_update_date`, `last_update_date`는 timezone 없는 원천값을 KST 벽시계로 해석해 UTC instant로 저장한다.
- 기존 EQP/TIP timestamp는 과거 Log Detail에 표시되던 원천 벽시계를 정답으로 삼아 9시간 앞당기는 data migration으로 보정한다.

## 2026-08-03: Access Stats 외부 사용량 동기화

- 외부 사용량 동기화 요청은 `access-stats` 접근이 허용된 모든 로그인 사용자에게 허용한다.
- 수동 통계 붙여넣기는 기존처럼 `access-stats`의 `admin` 역할만 허용한다.
- 일반 사용자의 실제 외부 API 동기화는 전역 기준 6시간에 한 번만 수행한다.
- `access-stats admin`과 슈퍼유저는 6시간 제한을 적용하지 않는다.
- 성공뿐 아니라 실패한 실제 시도도 일반 사용자의 6시간 제한에 포함해 장애 중 반복 호출을 막는다.
- 제한 기준은 `ExternalAppUsageSyncState.updated_at`이며, 제한된 요청은 외부 API 호출 없이 `skipped=true`와 사유를 반환한다.
- 프런트는 제한된 요청의 서버 사유를 정보 toast로 사용자에게 표시한다.

## 2026-08-12: Assistant 초기 마이그레이션 통합

- 서버 최초 적용 전인 `assistant`의 개발 마이그레이션 체인은 최종 모델 상태를 직접 생성하는 단일 `0001_initial.py`로 통합한다.
- 신규 설치에 불필요한 기존 메시지 연결 및 요약 이전용 data migration은 초기 마이그레이션에 포함하지 않는다.
- 단일 초기 마이그레이션이 배포된 이후의 Assistant schema 변경은 기존 파일을 수정하지 않고 새 migration으로 추가한다.

## 2026-08-12: Portal Assistant 앱 단위 활성 컨텍스트와 방 단위 공유 기억

- 같은 Assistant 대화방의 일반 앱(`assistant:openwebui:<appKey>`), Observer(`observer:*`), Email RAG(`assistant`)는 최근 모델 이력과 rolling summary를 `chatwidget:shared` 기억 그룹으로 공유한다.
- `contextKey`는 기억을 분리하지 않고 요청 sender, 메시지의 앱 출처와 현재 Observer 조회 범위를 보존한다.
- 앱 이동 시 대화방과 기억은 유지하고 현재 앱의 sender·고정 배경지식·화면 데이터만 교체한다.
- OpenWebUI의 앱 배경지식은 클라이언트 문장을 신뢰하지 않고 서버 허용 카탈로그에서 `appKey`를 해석해 system message에 추가한다.
- Observer의 공유 대화와 장기 요약은 질문 의도·용어·후속 질문을 이해하는 배경으로만 사용하고, 사실 판단은 현재 `observer_analysis_context_json`으로 제한한다.
- 기존 `assistant`와 `chatwidget:shared` rolling summary는 통합 전 메시지 집합의 `message_count`를 재사용할 수 없으므로 `0002` data migration에서 삭제하고 원본 메시지로 재생성한다.

## 2026-08-13: Assistant Runtime v2 Profile·partition·권한 provenance

- 이 결정은 2026-08-12의 모든 앱 공유 기억 결정을 대체한다. Portal은 `shared`, Email은 `shared`와 `scope:emails`, Observer는 `shared`와 `scope:observer`만 읽는다.
- 실행 의미는 versioned Profile로 재현하고 권한 하한은 항상 현재 Profile과 Tool 정책을 적용한다.
- `AssistantGeneration`을 Run source of truth로 유지하며 Run, message, summary, 자동 제목에 version 1 `access_requirements`를 저장한다.
- Account scope와 실제 RAG permission group/mailbox claim 중 하나라도 회수되면 답변 전체를 잠그고 내부 data claim 이름은 UI에 노출하지 않는다.
- client `history`를 받는 실행 API는 제공하지 않는다. `appKey`, `contextKey`는 권한 근거로 사용하지 않고 Turn service가 소유 대화방의 current branch를 서버에서 조립한다.
- legacy provenance는 nullable schema 이후 resumable command로 backfill하고 해석 불가능한 데이터는 `legacy-unresolved`로 영구 잠근다.
- 외부 LLM/RAG URL과 payload는 변경하지 않아 offsite dummy/env/Compose contract 수정은 하지 않는다.

## 2026-08-13: Email RAG 답변 Provider OpenWebUI 통합

- 이 결정은 위 Runtime v2 결정 중 Email 답변 Provider 연결을 유지한다는 부분만 대체한다.
- Email RAG의 검색, permission group/mailbox 필터, 구조화 `answer`/`segments`와 출처 계약은 유지한다.
- Email 답변 생성의 URL, model, token, 공통 header와 timeout은 일반 Assistant와 같은 `OPENWEBUI_*` 설정을 사용한다.
- `ASSISTANT_LLM_TEMPERATURE`와 `ASSISTANT_LLM_SYSTEM_MESSAGE`는 Email 구조화 prompt 조정값으로만 유지하고, `ASSISTANT_REQUEST_TIMEOUT`은 RAG 검색 timeout으로 유지한다.
- offsite `adfs_dummy`의 기존 OpenAI 호환 endpoint가 Email 구조화 stream을 지원하므로 mock handler나 Compose 서비스 계약은 변경하지 않는다.

## 2026-08-14: Appstore·ESOP Dashboard 서버 조회 배경지식

- Appstore와 ESOP Dashboard의 변경 가능한 업무 데이터는 RAG 색인 대신 domain selector를 통한 요청 시점 snapshot으로 조회한다.
- 브라우저는 검색·카테고리·선택 앱 또는 line·기간·화면 종류만 보내며 원본 업무 데이터는 보내지 않는다.
- Appstore와 ESOP는 각각 독립 Profile, Tool, `scope:appstore`/`scope:line-dashboard` 기억 partition과 대상 앱 Account scope를 사용한다.
- Appstore 연락처·댓글·이미지와 ESOP 사용자·댓글·수신자·관리자 설정은 snapshot에서 제외한다.
- snapshot은 untrusted read-only JSON으로 OpenWebUI system context에 결합하고 내부 문구를 명령으로 취급하지 않는다.
- 외부 OpenWebUI/RAG endpoint와 env, offsite dummy 계약은 변경하지 않는다.

## 2026-08-15: Assistant 앱 지식 자동 사용 Profile v2

- `email-rag` v2는 현재 질문과 권한 검증된 최근 대화를 먼저 분류하고, 메일 자료가 필요한 경우에만 `rag.search`를 실행한다.
- Appstore·Line Dashboard·Observer의 각 v2도 같은 판별 transport를 사용하고, 앱별 현재 데이터가 필요한 경우에만 selector 또는 분석 도구를 실행한다.
- 동적 도구가 필요 없는 질문은 tool key와 context snapshot 없이 일반 OpenWebUI 답변으로 전환하며, 고정 앱 설명은 최신 질문과 관련 있을 때만 참고한다.
- 일반 질문은 RAG를 조회하지 않으며 RAG tool key와 permission group/mailbox data claim도 저장하지 않는다.
- 메일 자료가 필요한 질문에서 관련 context를 찾지 못하면 일반지식으로 추측하지 않고 검색 결과 없음으로 답한다.
- 판별기는 후속 질문을 독립 검색 질의로 보완하며, 응답 오류나 형식 오류는 기존 RAG 사용 방식으로 fallback한다.
- 기존 동적 앱 Profile v1은 완료 Run replay의 실행 의미를 보존하기 위해 항상 지식 도구를 사용하는 동작으로 유지한다.
- 내장 dummy mode는 외부 판별 호출 없이 결정적 로컬 규칙을 사용하고, offsite OpenWebUI dummy endpoint는 동일한 구조화 판별 계약을 재현한다.
- 외부 RAG/OpenWebUI endpoint·env·Compose 계약은 변경하지 않는다.

## 2026-08-15: ChatWidget 현재 앱 전용·자동 지식 선택 모드

- 기존 ON/OFF 스위치는 `현재 앱 지식만 사용`과 `자동 지식 선택`의 명시적 2상태 선택기로 교체한다.
- 기본값인 현재 앱 전용 모드는 기존 앱별 Profile v2를 사용해 질문 의도는 판별하되 다른 앱 지식으로 전환하지 않는다.
- 자동 모드는 별도 `auto-knowledge` Profile에서 현재 앱을 우선하고, 다른 앱의 고유 업무 요청이 명확할 때만 Email·Observer·Appstore·Line Dashboard 중 하나를 선택한다.
- 자동 후보 Tool은 실행 전 현재 사용자 권한으로 필터링하며, 선택되지 않은 후보는 Tool 기록과 RAG data claim에 포함하지 않는다.
- Observer는 사용자 질문에 명시된 장비·기간·로그 유형을 현재 화면 범위보다 우선하고, 누락 필드는 현재 Observer 범위로 보완한다.
- 다른 앱에서 Observer 필수 범위를 확보하지 못하면 임의 값을 사용하지 않고 장비·기간·로그 유형을 묻는 명확화 답변을 반환한다.
- 자동 Profile은 권한 검증된 앱별 partition 기억을 읽되, 실행 결과는 실제 선택한 Tool의 권한 provenance만 저장한다.
- 기존 앱별 Profile v1/v2와 외부 API·DB·env 계약은 유지하므로 migration은 추가하지 않는다.

## 2026-08-04: Work Hub Grist OSS 전환

- Work Hub의 공동편집 원본은 Grist OSS document로 두고 Portal은 소속·접근 권한·document mapping과 자동화만 소유한다.
- Grist source는 vendor하거나 fork하지 않고 `gristlabs/grist-oss:1.7.13` image와 공식 REST API adapter로 격리한다.
- 공개 Portal 경로 `/work-hub`와 context API는 유지하고 외부 Webhook만 `/webhooks/grist`로 교체한다.
- `Affiliation.user_sdwt_prod` 하나당 Grist document 하나를 대응시키며 Equipment, WorkLog, Task table ID 계약을 유지한다.
- OIDC/prod는 Portal과 같은 IdP의 별도 Grist OIDC client를 사용하고 document email ACL은 Portal 소속에서 동기화한다.
- 기존 Baserow 업무 데이터는 자동 이관하지 않으며 기존 mapping은 비활성화하고 Baserow volume은 명시적 폐기 전까지 보존한다.

## 2026-08-04: Work Hub APITable OSS와 Portal 단일 로그인 전환

- Work Hub의 공동편집 원본을 APITable Space의 Equipment, WorkLog, Task datasheet로 전환한다.
- Portal 로그인을 유일한 사용자 인증으로 사용하며 별도 APITable OIDC client나 로그인 화면을 사용자 흐름에 두지 않는다.
- Portal은 권한 재검사 후 60초 수명의 HS256 1회용 ticket을 발급하고, APITable overlay는 `jti` 재사용을 Redis에서 거부한 뒤 session을 발급한다.
- APITable upstream grid와 공동편집 엔진은 수정하지 않고 고정 image digest 위에 SSO/provisioning controller만 overlay한다.
- Equipment의 자동 동기화 field는 field role로 잠그고, WorkLog는 Attachment와 작성·수정자/시각 field를 사용한다.
- Grist volume과 기존 Django Grist table은 검증 기간 동안 삭제하지 않아 기능 플래그와 이전 adapter로 원복할 수 있게 한다.

## 2026-08-05: Portal 기준 APITable 접근 권한 projection

- APITable Space 멤버와 managed datasheet 역할의 단일 원본은 Portal account의 현재 소속, `UserSdwtProdAccess`, 사용자·소속 활성 상태로 고정한다.
- 현재 소속 사용자는 최소 `member`로 보고 명시 `manager`는 유지하며, 추가 소속의 `viewer/member/manager`를 APITable `reader/editor/manager`로 투영한다.
- Portal 변경은 같은 DB transaction에 `APITableAccessSyncOutbox`를 적재하고 commit 후 즉시 처리한다.
- APITable 장애는 Portal 소속 변경을 되돌리지 않으며 API 컨테이너의 Outbox loop가 지수 backoff로 재시도한다.
- 동기화는 delta가 아니라 소속별 전체 desired state를 사용하며 Portal 목록에서 사라진 사용자는 Space에서 제거한다.
- `sync_apitable_access --all`은 APITable 직접 변경이나 누락 이벤트를 Portal 기준으로 복구하는 전체 reconciliation 경로로 유지한다.

## 2026-08-05: Work Hub Grist OSS 재전환

- APITable 실행 경로와 Portal overlay를 제거하고 보존된 Grist document mapping과 공식 REST API adapter를 다시 활성화한다.
- APITable migration과 table은 적용 이력을 수정하거나 삭제하지 않고 새 migration에서 활성 mapping만 비활성화한다.
- Portal 기준 접근 권한 단일 원본과 Outbox 방식은 유지하며 `viewer/member/manager`를 Grist `viewers/editors/owners`로 투영한다.
- Grist 장애는 Portal 소속 변경을 되돌리지 않으며 `GristAccessSyncOutbox` worker가 지수 backoff로 재시도한다.
- Portal 요청은 `GristAccessSyncOutbox` 적재까지만 수행하고 외부 ACL 호출은 독립 `work-hub-access-worker`가 전담한다.
- 완료된 Grist ACL Outbox는 기본 30일 보존 후 worker가 정리하며 실패·terminal·processing 이력은 자동 삭제하지 않는다.
- `/work-hub`, context API, Equipment/WorkLog/Task 계약은 유지하고 Webhook은 `/webhooks/grist`를 사용한다.

## 2026-08-05: Work Hub Portal account forward-auth 인증

- Grist 외부 boot 화면과 Grist 전용 OIDC client를 제거하고 Portal `account.User`를 브라우저 인증 identity의 단일 원본으로 사용한다.
- Grist OSS에 포함되지 않은 GristConnect 대신 공식 forward-auth를 사용하고 Grist container 포트는 Nginx 내부 upstream으로만 노출한다.
- `/auth/grist/login`은 Portal 사용자 PK를 30초 ticket으로 서명하고 `/auth/grist/verify`는 현재 account·Portal·`work-hub` 접근을 재검사해 email을 반환한다.
- Nginx는 검증 성공 email만 `X-Forwarded-User`로 전달하고 일반 경로의 외부 header와 `/boot` 접근을 차단한다.
- schema·record·ACL·Webhook 자동화는 Portal 관리자 Grist account에서 발급한 API key를 server-to-server credential로 유지한다.

## 2026-08-05: Work Hub Grist widget 격리

- Grouped View는 Grist core fork나 image 재빌드 대신 `GRIST_USER_ROOT/plugins`의 고정 revision user plugin으로 제공한다.
- 자체 호스팅 widget은 Grist main app과 다른 origin에서 실행하고 Nginx는 등록된 plugin 정적 경로만 공개한다.
- widget은 `read table`만 요청하며 외부 runtime dependency를 제거하고 CSP로 외부 연결을 차단한다.
- 외부 공식 widget 목록 장애는 `GRIST_WIDGET_LIST_URL_OPTIONAL=true`로 격리해 자체 호스팅 widget gallery를 유지한다.

## 2026-08-10: Work Hub 미적용 migration 통합

- 실제 서버에는 Work Hub migration이 적용되지 않았으므로 테스트 환경의 Baserow→Grist→APITable→Grist 전환 이력을 운영 migration으로 유지하지 않는다.
- Baserow/APITable 호환 모델과 table은 최종 schema에서 제거하고 Grist 모델 4개만 유지한다.
- `work-hub` AccessScope 생성과 Grist schema 생성을 `work_hub.0001_initial` 하나로 통합한다.
- 이 결정은 2026-08-05의 APITable migration/table 보존 결정을 대체한다.

## 2026-08-10: Work Hub Grist ACL 권한 원본 강화

- Grist document ACL 대상은 Portal 소속 역할과 Portal·`work-hub` 최종 앱 접근을 모두 통과한 사용자로 제한한다.
- 사용자 앱 권한, Portal/Work Hub 부서 정책, scope 활성 상태와 사용자 부서 변경은 Grist 접근 Outbox를 재생성한다.
- document의 `maxInheritedRole`은 `null`로 고정해 workspace/org 상속 권한이 Portal desired state를 우회하지 못하게 한다.
- 재시도 불가능한 Grist 설정·4xx·응답 계약 오류는 `terminal` 상태로 보존하고, 새 권한 변경이 발생할 때만 다시 처리한다.
- 동일 Webhook receipt와 WorkLog별 Task link는 외부 Grist 호출 동안 DB 잠금을 유지해 동시 전달에서도 Task를 하나만 생성한다.
- 이메일이 등록된 활성 Portal superuser는 소속 membership 유무와 관계없이 모든 활성 Grist document의 owner로 투영한다.

## 2026-08-10: Work Hub mapping과 완료 이력 계약

- 운영 Grist document가 없는 초기 도입 시점부터 소속 mapping의 `doc_id`는 불변 식별자로 취급한다.
- mapping 생성과 동일 document metadata 갱신은 ACL Outbox를 자동 적재한다.
- `WORK_HUB_ENABLED=0`은 launcher뿐 아니라 미로그인 사용자의 Portal 인증 진입 전 Grist forward-auth login과 ticket 검증도 차단한다.
- 완료 Outbox와 완료 Webhook receipt는 기본 30일, 실패 Webhook receipt는 기본 90일 보존하며 전용 worker가 주기적으로 정리한다.

## 2026-08-10: Work Hub 최소 보안·정합성 보강

- `GRIST_WEBHOOK_SECRET`은 document에 저장하는 공용 credential이 아니라 document·table 전용 HMAC token을 파생하는 마스터 키로 사용한다.
- 전용 worker는 기존 기본 1시간 정리 주기마다 전체 document ACL을 Portal desired state와 맞추며 개별 document 실패는 격리한다.
- OIDC·운영 Grist는 `GRIST_SESSION_SECRET`이 비어 있으면 시작하지 않고, 개발 환경만 로컬 기본값을 유지한다.
- launcher의 타이머 자동 이동은 현재 history를 교체하고 사용자가 누르는 열기 버튼은 기존 history 추가 동작을 유지한다.

## 2026-08-10: Work Hub 새 volume 무입력 초기화

- 새 `grist_data`에서는 기존 API key 문자열이 유효하지 않으므로 `grist-api-key-init`이 `GRIST_ADMIN_EMAIL`의 Grist 공식 profile API key를 첫 기동에 발급한다.
- API key는 환경 변수보다 `${WORK_HUB_SECRET_HOST_PATH}/grist_api_key` 파일을 차선으로 사용하며 API와 worker는 read-only로 mount한다.
- OIDC(stage)와 prod의 host, 관리자, session/Webhook/forward-auth ticket key는 각각 `env/work-hub.oidc.env`, `env/work-hub.prod.env`를 Compose interpolation 기본값으로 사용한다.
- stage Grist/widget host는 `worklog.stg.plane.samsungds.net`, `widgets.worklog.stg.plane.samsungds.net`, prod는 `worklog.plane.samsungds.net`, `widgets.worklog.plane.samsungds.net`으로 고정한다.
- 일반 app target은 Work Hub를 끈 상태를 유지하고 `make oidc-work-hub-up`, `make prod-work-hub-up`만 기능 플래그와 bootstrap dependency를 함께 활성화한다.
- `GRIST_ADMIN_EMAIL`은 Portal 일반 역할과 겹쳐도 모든 관리 document의 명시적 `owners`로 유지하고, ACL에 없으면 자동 추가한다.
- `make prod-work-hub-up`은 API·Web image build와 같은 API image의 one-off DB migration을 성공한 뒤만 서비스를 기동한다.
- OIDC·운영 원복은 `*-work-hub-disable`로 Grist session 정리를 유예한 뒤 `*-work-hub-down`으로 worker·initializer·Grist를 제거하는 2단계로 수행한다.

## 2026-08-11: Work Hub Webhook 비동기 처리와 운영 fail-closed

- Grist Webhook HTTP 경계는 document·table token, mapping과 payload를 검증해 `GristWebhookReceipt`에 저장한 뒤 `202 Accepted`로 종료한다.
- `work-hub-access-worker`가 검증 payload를 임대해 Task를 생성·연결하며, 재시도 가능한 실패는 지수 backoff로 처리하고 중단된 임대는 회수한다.
- 동일 receipt나 WorkLog row가 처리 중이면 요청 thread나 worker가 DB를 반복 조회하지 않고 기존 작업 유지 또는 receipt 재시도로 전환한다.
- 운영 Work Hub migration은 구버전 API·worker를 먼저 중지하고, 실패 시 신버전을 올리지 않는 fail-closed를 사용한다.
- 운영 긴급 비활성화는 비활성 Web build보다 API·Nginx·worker의 기능 OFF 재생성을 먼저 수행한다.
- Grist API key initializer의 모든 HTTP 요청은 연결 3초, 전체 응답 15초 상한을 사용한다.

## 2026-08-14: Work Hub Grist 원격 서버 분리

- 기존 Portal 서버에는 Django API, Account DB, Web, `work-hub-access-worker`를 유지하고 새 서버 `10.172.117.91`에는 Grist OSS, 전용 Nginx, widget, API key initializer만 실행한다.
- 새 서버는 독립 `docker-compose.grist.yml` project와 `tailwind_grist_remote_data` named volume을 사용하며 일반 down은 volume과 bootstrap key 파일을 삭제하지 않는다.
- 새 서버 initializer가 생성한 관리자 API key는 파일 공유 mount 대신 기존 Portal 서버의 `GRIST_API_KEY` 배포 secret으로 전달한다.
- 새 서버 Nginx는 기존 Portal의 `/auth/grist/verify`를 원격 forward-auth 경계로 사용하고, Portal은 Grist REST API를 `http://10.172.117.91`로 호출한다.
- 비활성화와 원복은 Portal 측 `*-work-hub-disable/down`과 새 서버 측 `grist-remote-disable/down`을 함께 실행한다.
- 초기 배포는 IP 기반 HTTP로 시작하고 DNS·TLS 전환 시 공개 URL과 Portal 허용 origin 계약을 env로 함께 변경한다.
