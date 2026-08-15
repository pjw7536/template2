# ExecPlan: ChatWidget 지식 라우팅 v2

## 목표
- Portal 및 지식 미지원 앱에서 업무 지식 자동 사용을 기본 ON으로 제공하고 OFF에서는 일반 답변만 생성한다.
- Emails, Observer, Appstore, Line Dashboard에서는 현재 화면을 기본값으로 제공하고 자동 모드를 선택할 수 있게 한다.
- 질문마다 `direct | retrieve | clarify`와 단일 지식 앱을 결정하며, 실행 결과를 안전한 `knowledgeContext`로 저장·응답한다.
- 기존 `auto-knowledge` v1 replay 의미와 작업 트리의 메일 링크·ChatWidgetPanel 헤더 변경을 보존한다.

## 현재 상태
- 프론트엔드는 `surfaceConfig.js`에서 Portal, 앱별 현재 화면, 기존 `auto-knowledge` v1 surface를 구성한다.
- 백엔드는 `profiles.py`, `knowledge_intent.py`, `runtime.py`, `turns.py`에 기존 앱별 profile 및 자동 라우팅 v1 흐름이 있다.
- `AssistantGeneration.execution_metadata` JSONField가 있어 DB schema 변경 없이 실행 메타데이터를 확장할 수 있다.
- 작업 트리의 기존 변경은 이메일 근거 링크의 현재 창 이동과 ChatWidgetPanel selector의 헤더 배치이며 반드시 보존한다.

## 범위
- 수정: assistant 프론트엔드 capability/mode/surface/UI/message provenance 및 Emails page context.
- 수정: assistant profile v2, 라우팅 정규화·fallback·단일 도구 실행, 이메일 scope 권한 재검증, 응답 serializer.
- 수정: 관련 React/Vitest 및 Django assistant/emails 테스트.
- 제외: DB migration, 외부 RAG API, env/Compose, 신규 지식 provider, transient 이메일 목록 검색·날짜 필터.

## 설계
- 프론트엔드 capability registry가 `current_scope` 지원 앱을 명시하고 route가 바뀔 때 앱 기본 모드를 다시 적용한다. 모드는 영구 저장하지 않는다.
- 기존 Turn 요청의 `profileKey/profileVersion/appContextKey/toolInputs` shape를 유지하고, Emails 현재 화면에서만 `rag.search.mailbox/emailId`를 선택적으로 보낸다.
- `auto-knowledge` v2는 라우터가 `direct | retrieve | clarify` 및 nullable 단일 `sourceApp`을 반환하도록 정규화한다. `current_scope` profile은 후보를 현재 앱 하나로 제한한다.
- `direct`는 지식 설명을 주입하지 않는다. `retrieve`는 선택 도구를 한 번만 실행하며 앱별 2차 intent 판별을 건너뛴다.
- 라우터는 한 번 재시도하고 실패하면 제한 prompt를 사용한 일반 답변으로 전환하며 fallback을 기록한다. 검색 근거가 없으면 업무 사실을 일반지식으로 대체하지 않는다.
- 서버는 사용자 access claims로 후보 앱을 제한하고 Emails mailbox/emailId를 selector로 재검증한다.
- 응답 `knowledgeContext`는 `mode`, `route`, `sourceApp`, `grounded`, `fallback`만 노출한다. raw query·권한 그룹·index명은 노출하지 않는다.
- migration/env/auth 영향: schema·env 변경 없음. 기존 권한 정보를 실행 전에 재사용·재검증한다.

## 실행 단계
- [x] 기존 v1 프론트엔드·백엔드 흐름과 테스트 계약을 정밀 확인한다.
- [x] capability registry, 기본 모드 전환, Emails page context, 제어 UI와 provenance를 구현한다.
- [x] auto-knowledge v2 profile, 라우팅/fallback/grounding/권한 검증 및 API 정규화를 구현한다.
- [x] 프론트엔드와 백엔드 회귀 테스트를 추가·수정한다.
- [x] 관련 테스트, migration check, lint 및 경계/UI 감사를 실행하고 결과를 기록한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.assistant api.emails`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- 관련 Vitest와 ESLint
- `npm run agent:audit:ui`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:api-boundary`
- 기대 결과: 신규 v2와 기존 v1 테스트가 통과하고 migration이 생성되지 않으며 신규 경계 위반이 없다.
- 결과: 관련 Vitest 108개와 Django `api.assistant api.emails` 147개가 통과했다.
- 결과: 변경 frontend ESLint, UI/frontend/backend boundary audit가 모두 통과했다.
- 결과: `makemigrations --check --dry-run`은 `No changes detected`였다.
- 환경 참고: `api` 서비스가 실행 중이 아니어서 `exec` 대신 동일 이미지의 `docker compose run --rm --no-deps --entrypoint python api ...`로 Django 검증을 수행했다.

## 위험과 대응
- 위험: v1 저장 Turn replay가 최신 profile로 해석될 수 있다.
- 대응: `(profileKey, profileVersion)` registry에 v2를 추가하고 요청·저장 version을 그대로 사용한다.
- 위험: client scope 조작으로 다른 mailbox/email에 접근할 수 있다.
- 대응: access claims 후보 제한에 더해 mailbox와 email ID를 서버 selector로 재검증한다.
- 위험: 라우터/검색 실패가 확인되지 않은 업무 사실 생성으로 이어질 수 있다.
- 대응: fallback 제한 prompt와 근거 없음 응답 gate를 분리하고 구조화 metadata로 검증한다.
- 위험: 기존 작업 트리 변경과 충돌할 수 있다.
- 대응: 네 파일의 기존 diff를 기준선으로 유지하고 변경 후 diff에서 보존 여부를 재확인한다.

## 진행 기록
- 2026-08-15: 요청 계획, 저장소 규칙, 기존 작업 트리 diff를 확인하고 ExecPlan을 작성했다. Hard-Block은 없으며 DB·외부 RAG·env/Compose는 변경하지 않기로 확정했다.
- 2026-08-15: capability 기반 기본 모드, Portal·미지원 앱 switch, Emails page scope, v2 단일 앱 라우터와 안전 fallback, 서버 scope 재검증, `knowledgeContext` 응답을 구현했다.
- 2026-08-15: v2 grounding gate와 명시적 auto v1 재실행을 분리해 v1 도구 실행 의미를 보존했다.
- 2026-08-15: 관련 frontend 108개, backend 147개 테스트와 ESLint, migration check, UI·frontend·backend 경계 감사를 모두 통과해 구현을 완료했다.
