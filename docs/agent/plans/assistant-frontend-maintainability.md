# ExecPlan: Assistant frontend 유지보수성 개선

## 목표
- `useChatSession` 공개 계약과 사용자 동작을 유지하면서 대화방·메시지·Turn 책임을 작은 Hook으로 분리한다.
- React Query cache 전체 구독과 인증 없는 로컬 대화 fallback을 제거한다.
- 화면별 Profile, app context, Tool 입력 조합을 하나의 순수 함수로 관리한다.
- ChatWidget의 창 이동·크기 조절 상태를 대화 실행 책임과 분리한다.

## 현재 상태
- `useChatSession.js`는 대화방, 메시지, Turn, cache mutation, 피드백과 내보내기를 한 파일에서 관리한다.
- React Query 결과 대신 `getQueryData()`를 조립하고 cache 전체 변경을 revision state로 구독한다.
- 제품 route는 인증·Assistant 권한을 통과한 사용자에게만 Widget을 렌더링하지만 Hook에는 비저장 fallback 분기가 남아 있다.
- `ChatWidget.jsx`가 실행 surface 결정과 floating window pointer lifecycle을 함께 소유한다.
- frontend/backend boundary audit는 현재 통과한다.

## 범위
- 수정: `apps/web/src/features/assistant/hooks`, `components/ChatWidget.jsx`, `pages/ChatPage.jsx`.
- 추가: Assistant session 내부 Hook, floating window Hook, `lib/assistant` surface resolver와 테스트.
- 수정: 관련 frontend 회귀 테스트와 이 ExecPlan.
- 미수정: Assistant backend API, DB schema, 권한 규칙, SSE event와 UI 디자인.

## 설계
- `useChatSession`은 소비자가 사용하는 façade로 유지하고 반환 필드 이름을 바꾸지 않는다.
- `useAssistantConversations`가 목록·검색·보관·대화방 mutation과 title/export를 소유한다.
- `useAssistantMessages`가 활성 메시지 query·이전 내역·pending cache·feedback/reset을 소유한다.
- `useAssistantTurns`가 send/edit/regenerate/retry/stop과 streaming 임시 메시지를 소유한다.
- Query 결과는 `useQuery().data`를 렌더 원본으로 사용하고 cache 전체 subscribe를 사용하지 않는다.
- `userKey`는 필수이며 인증이 준비되지 않은 화면은 session Hook을 mount하지 않는다.
- `resolveAssistantSurface`는 app key와 page/RAG context를 `{mode, profileKey, profileVersion, appContextKey, toolInputs}`로 변환한다.
- `useFloatingChatWindow`는 launcher/widget 위치, drag, resize, maximize와 sidebar resize를 관리한다.

## 실행 단계
- [x] surface resolver와 인증 전용 렌더 계약을 추가한다.
- [x] 대화방·메시지·Turn Hook을 추출하고 façade를 축소한다.
- [x] cache 전체 강제 구독과 `persistenceEnabled` 분기를 제거한다.
- [x] floating window lifecycle을 전용 Hook으로 옮긴다.
- [x] 기존 회귀 테스트를 갱신하고 전체 frontend 검증을 실행한다.

## 검증
- `npm run web:test`
- `npm run web:lint`
- `npm run web:build`
- `scripts/agent/check_frontend_boundaries.sh`
- `npm run agent:audit:ui`
- `git diff --check`

## 위험과 대응
- 위험: optimistic message와 서버 완료 message 교체 순서가 달라질 수 있다.
- 대응: 공개 Hook 회귀 테스트와 send/retry/edit/regenerate 테스트를 그대로 유지한다.
- 위험: query pagination cache shape 변경으로 이전 메시지나 검색 결과가 유실될 수 있다.
- 대응: 기존 query key와 cache shape를 유지하고 구독 방식만 `useQuery().data`로 바꾼다.
- 위험: 인증 초기화 중 Hook 호출 순서가 달라질 수 있다.
- 대응: session을 사용하는 content component를 인증된 경우에만 mount한다.
- 위험: pointer lifecycle 추출 중 drag/resize 동작이 바뀔 수 있다.
- 대응: 기존 handler 계약과 bounds utility를 유지하고 Widget 테스트와 build를 실행한다.

## 진행 기록
- 2026-08-13: 현재 구조와 audit 결과를 검토하고 backend는 유지, frontend 상태 조립만 개선하기로 결정했다.
- 2026-08-13: `resolveAssistantSurface`를 추가해 Portal/Email/Observer의 Profile·context·Tool 입력 결정을 단일화했다.
- 2026-08-13: `useChatSession`을 façade로 축소하고 대화방, 메시지, Turn 책임을 각각의 Hook으로 분리했다.
- 2026-08-13: React Query cache 전체 구독과 인증 없는 비저장 fallback을 제거했다.
- 2026-08-13: launcher, drag, resize, maximize, sidebar resize를 `useFloatingChatWindow`로 이동했다.
- 2026-08-13: Web 테스트 164개, lint, production build, 전체 agent audit와 `git diff --check`가 통과했다.
