# ExecPlan: ChatWidget 앱 배경지식 선택 모드

## 목표
- ChatWidget 상단에서 일반 대화와 현재 앱 배경지식 사용을 명시적으로 선택할 수 있게 한다.
- 앱 진입 시 앱 배경지식을 기본으로 사용하고, Emails와 Observer에서도 일반 대화를 선택하면 전용 도구를 비활성화한다.

## 현재 상태
- `apps/web/src/lib/assistant/surfaceConfig.js`가 앱별 Profile, context key, Tool 입력을 결정한다.
- `apps/web/src/features/assistant/components/ChatWidget.jsx`가 현재 앱 surface를 `useChatSession`에 전달한다.
- 전체 Assistant 화면은 `assistant:openwebui:assistant`를 일반 대화 context로 이미 사용한다.
- ChatWidget 헤더 아래에는 Observer/Emails/일반 앱의 연결 상태가 조건부로 표시된다.

## 범위
- Assistant frontend의 surface 선택, ChatWidget 상태, compact 선택 UI와 관련 테스트를 수정한다.
- 대화방 저장 구조, backend Profile/context 검증, DB schema, auth/env 계약은 변경하지 않는다.
- 기존 OpenWebUI Portal context 누락 수정은 보존한다.

## 설계
- 앱별 surface 해석기에 `useAppContext` 선택을 추가하고, `false`이면 기존 Assistant 일반 surface를 반환한다.
- ChatWidget은 현재 앱 key별 선택 상태를 관리하며 앱 key가 바뀌면 앱 배경지식 사용을 기본값으로 계산한다.
- native radio semantics를 사용하는 compact segmented control을 헤더의 고정 영역에 배치한다.
- 일반 대화에서는 Emails RAG 설정과 Observer page context를 `useChatSession`에 전달하지 않는다.
- public facade, migration, env, auth 변경은 없다. Offsite mock/dev wiring 변경도 필요하지 않다.

## 실행 단계
- [x] surface 해석기에 일반 대화 선택과 테스트를 추가한다.
- [x] ChatWidget에서 앱별 기본 상태와 Turn surface 전환을 연결한다.
- [x] 접근 가능한 context mode selector와 상태별 안내를 추가한다.
- [x] ChatWidget 및 selector 회귀 테스트를 추가한다.
- [x] frontend 테스트, lint, UI/경계 감사를 실행한다.

## 검증
- `npm --prefix apps/web run test:run -- src/lib/assistant/surfaceConfig.test.js src/features/assistant/components/ChatWidget.test.jsx src/features/assistant/components/ChatContextModeSelector.test.jsx`
- `npm --prefix apps/web run lint -- src/lib/assistant/surfaceConfig.js src/lib/assistant/surfaceConfig.test.js src/features/assistant/components/ChatWidget.jsx src/features/assistant/components/ChatWidget.test.jsx src/features/assistant/components/ChatWidgetPanel.jsx src/features/assistant/components/ChatContextModeSelector.jsx src/features/assistant/components/ChatContextModeSelector.test.jsx`
- `npm --prefix apps/web run build`
- `npm run agent:audit:ui`
- `npm run agent:audit:web-boundary`

## 위험과 대응
- 위험: 모드 변경 시 현재 대화방이 초기화되거나 별도 대화방이 생성될 수 있다.
- 대응: `useChatSession` 인스턴스를 유지하고 Turn별 Profile/context 옵션만 갱신한다.
- 위험: 일반 대화인데 Emails RAG 또는 Observer 분석 입력이 남을 수 있다.
- 대응: 일반 surface는 `portal-default`, 빈 Tool 입력, `assistant:openwebui:assistant` 조합만 반환하도록 테스트한다.
- 위험: 답변 생성 중 모드 표시와 실행 context가 달라질 수 있다.
- 대응: 생성 중 radio를 비활성화한다.

## 진행 기록
- 2026-08-13: 권장안(앱 지식 기본 사용, Emails/Observer 동일 적용, 앱 이동 시 기본값 초기화)으로 설계를 확정했다.
- 2026-08-13: 일반/앱 surface 전환, native radio selector, 앱 이동 초기화와 회귀 테스트를 구현했다.
- 2026-08-13: 관련 Vitest 19개, lint, production build, UI 일관성 감사와 frontend 경계 감사를 통과했다. DB migration과 offsite mock/env 변경은 필요하지 않았다.
