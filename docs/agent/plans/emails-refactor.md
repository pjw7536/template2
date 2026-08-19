# ExecPlan: Emails 수집·mailbox·OCR·Outbox/RAG 단일화

## 목표
- 메일 수집, 조회, 이동, 삭제, OCR, Outbox/RAG와 mailbox 분류 책임을 단순화한다.
- 업무 메일과 RAG/outbox 상태를 손실 없이 보존한다.

## 현재 상태
- `views.py` 1,042줄, `selectors.py` 1,099줄, `tests.py` 2,677줄이다.
- input은 `email_ids/emailIds`, `to_user_sdwt_prod/toUserSdwtProd`, query `user_sdwt_prod/userSdwtProd`를 함께 허용한다.
- Account affiliation/data-scope, MinIO, POP3, OCR internal token, RAG adapter와 Mail API가 연결돼 있다.

## 범위
- 수정: `api.emails`, frontend emails, Account/RAG/common facade 소비, Airflow/command/dummy/env/docs/tests.
- 유지: `/emails/**` 화면/API, source/target mailbox 권한, unassigned fallback, Email/Asset/Outbox row와 OCR/RAG eventual consistency.

## 설계
- view를 inbox/sent/mailboxes/assets/ocr/ingest/outbox/mutations module로 나누고 selector는 list/detail/mailbox summary로 분리한다.
- JSON/query는 `emailIds`, `toUserSdwtProd`, `userSdwtProd`만 허용하고 snake_case alias는 400 처리한다.
- mailbox canonical 값은 active Account affiliation의 userSdwtProd이며 분류 불가 메일은 `UNASSIGNED_USER_SDWT_PROD`에 보존한다.
- move/delete는 source와 target capability를 transaction 시작 후 재검사하고 storage/RAG side effect는 Outbox로만 예약한다.
- ingest는 POP3 message identity dedup→Email/Asset write→Outbox enqueue 순서를 한 transaction으로 수행한다.
- OCR claim/update는 internal token과 claim state transition을 유지한다.
- RAG 호출은 공통 adapter만 사용하고 provider 실패 시 Email 원본은 유지하며 Outbox retry 상태를 남긴다.
- frontend server state는 React Query만 소유하고 selected email, split pane size, selection set만 local state로 둔다.
- schema/migration 변화는 없다.

## 실행 단계
- [x] mailbox/access/ingest/OCR/outbox mutation characterization을 고정한다.
- [x] snake_case frontend/test 소비자를 전환하고 alias를 제거한다.
- [x] view/selector/test와 frontend controller를 책임별로 분리한다.
- [x] RAG adapter와 storage compensation을 연결한다.
- [x] offsite Mail/RAG dummy, OCR token과 POP3 parser/설정 안전 실패 흐름을 검증한다.

## 검증
- dev API container에서 `api.emails api.account api.rag api.assistant` tests.
- frontend Emails tests/lint/build.
- dummy POP3/RAG/Mail/OCR smoke, retry/idempotency/permission race tests.
- migration drift, boundary/UI/docs audit.

## 위험과 대응
- 위험: 이동/삭제와 RAG index가 불일치한다.
- 대응: DB transaction에는 Outbox만 쓰고 provider 반영은 idempotent retry로 수렴시킨다.
- 위험: legacy mailbox alias 제거가 저장된 row를 고립시킨다.
- 대응: API alias만 제거하고 DB의 기존 userSdwtProd/UNASSIGNED 값은 그대로 유지한다.

## 의존성과 복구
- 상위 계약: [마스터](repository-refactor-master-2026-08.md), [Account](account-refactor.md), [RAG Adapter](rag-common-adapter-refactor.md). Assistant Email context의 선행 단계다.
- 복구: API/frontend/service를 함께 revert하고 pending Outbox를 idempotent worker로 계속 처리한다. Email/Asset 원본과 mailbox 값은 삭제하지 않는다.

## 진행 기록
- 2026-08-18: 세 snake_case HTTP alias 제거와 unassigned 장애 fallback 유지를 확정했다.
- 2026-08-18: HTTP 입력을 camelCase로 단일화하고 unknown query/body를 거부했다. view·selector를 책임별 package로, test를 mailbox/endpoint 그룹으로 분리했으며 Emails 68개와 frontend 195개 회귀가 통과했다.
- 2026-08-18: dev dummy에는 HTTP Mail sandbox만 있고 POP3 protocol server는 없음을 확인했다. 새 protocol emulator를 추가하지 않고 POP3는 parser/transport test와 미설정 fail-closed로, Mail/RAG는 실제 dummy smoke로 검증하도록 계획을 재동결했다.
- 2026-08-18: POP3 설정을 Django `EMAIL_POP3_*`로 단일화하고 구 `POP3_*` runtime fallback과 `run_pop3_ingest_from_env` symbol을 제거했다. dev OCR token wiring을 보완했으며 Mail 생성/삭제, RAG index-info, OCR wrong-token 401 smoke를 통과했다. Emails·Account·RAG·Assistant 365개, frontend 195개, lint/build, migration drift와 경계/UI/hotspot 검사가 모두 통과했다.
