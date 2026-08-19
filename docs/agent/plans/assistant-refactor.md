# ExecPlan: Assistant 대화·runtime·UI 단일화

## 목표
- 대화·메시지·generation·summary, provenance, SSE runtime과 page/widget 중복을 정리한다.
- `legacy-unresolved` fail-closed와 domain context 권한 하한을 보존한다.

## 현재 상태
- backend tests 2,626줄, `turns.py` 904줄, views 752줄이며 frontend 55개 파일/9,103줄이다.
- Run source of truth, Profile version, memory partition, version 1 accessRequirements와 resumable backfill command가 구현돼 있다.
- Assistant page와 ChatWidget이 conversation/message/turn UI lifecycle을 중복 조립한다.
- Account, RAG, Emails, Observer, AppStore, Line Dashboard context를 소비한다.

## 범위
- 수정: `api.assistant`, frontend assistant, 포함 domain public context facade, RAG/OpenWebUI dummy/env/docs/tests.
- 유지: `/assistant`, ChatWidget, `/api/v1/assistant/**`, SSE event 의미, stored conversations/messages/generations/summaries/feedback.
- 제외: 모든 Spider·Teamstaff profile, app context, scope, branding entry 변경.

## 설계
- conversation service는 CRUD/title/export/summary, turn service는 validate→authorize→snapshot→run fence→stream→persist만 담당한다.
- `AssistantGeneration`이 Run source of truth이고 message/summary/title accessRequirements는 생성 근거를 합집합으로 보존한다.
- unknown provenance/version/partition은 영구 `legacy-unresolved`로 잠그며 자동 완화하지 않는다.
- backfill command는 batch/resume/dry-run/count report를 유지하고 성공 분류 시 sentinel을 실제 requirements로 교체한다.
- SSE event는 `run`, `delta`, `source`, `message`, `error`, `done` canonical event와 camelCase data를 사용하며 client disconnect는 provider 호출을 취소한다.
- frontend page와 widget은 동일 conversation/message/turn controller와 React Query cache를 사용하고 window/resize/open state만 각각 local UI state로 둔다.
- domain tool은 server-side selector/service snapshot만 받고 browser context는 filter 입력으로만 사용한다.
- current schema는 유지하고 migration은 없다. backfill 완료 전 legacy row 삭제도 없다.

## 실행 단계
- [x] conversation/SSE/provenance/profile/tool characterization을 고정한다.
- [x] backend view/turn/runtime/test를 responsibility module로 분리한다.
- [x] page/widget 공통 controller와 message renderer를 추출한다.
- [x] Account/RAG/Emails/Observer/AppStore/Line Dashboard context 회귀를 검증한다.
- [x] offsite OpenWebUI/RAG dummy와 backfill command를 검증한다.
- [x] 포함 feature 외 app context snapshot이 불변인지 확인한다.

## 검증
- dev API container에서 `api.assistant api.account api.rag api.emails api.observer api.appstore api.drone` tests.
- frontend Assistant tests/lint/build.
- SSE cancel/timeout/retry/reconnect, concurrent run fence, provenance revocation, backfill idempotency tests.
- dummy OpenWebUI/RAG smoke, migration drift, boundary/hotspot/UI audit.

## 위험과 대응
- 위험: page/widget cache 통합으로 방이나 scroll state가 섞인다.
- 대응: server entity cache와 surface-local UI state key를 분리해 두 surface 동시 mount test를 둔다.
- 위험: provenance 단순화가 과거 답변을 과도하게 노출한다.
- 대응: unknown은 항상 `legacy-unresolved` fail-closed로 유지한다.

## 의존성과 복구
- 상위 계약: [마스터](repository-refactor-master-2026-08.md), Account/RAG/Emails/Observer/AppStore/Line Dashboard 계획. Home shell이 Assistant widget을 최종 조립한다.
- 복구: schema migration이 없으므로 runtime/UI를 revert한다. 생성 중 Run은 fence 후 실패 처리하며 저장 대화/message/provenance는 보존한다.

## 진행 기록
- 2026-08-18: current Profile/runtime v2와 legacy fail-closed를 불변 계약으로 확정했다.
- 2026-08-18: HTTP view와 tests를 conversation/message/export/RAG/Turn 책임으로 분리하고, Turn 입력·권한 계약을 실행·저장 수명주기에서 분리했다. page/widget은 `useAssistantChatController`로 동일 session/composer lifecycle을 사용한다. 포함 domain 765개와 frontend 195개 테스트, lint/build, OpenWebUI/RAG dummy smoke, backfill dry-run, migration drift 및 전체 감사를 통과했으며 Spider·Teamstaff product path는 변경하지 않았다.
