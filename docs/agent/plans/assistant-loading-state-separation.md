# ExecPlan: Assistant 이력 로딩과 답변 생성 상태 분리

## 목표
- 대화방 이동 중 `RAG 배경지식을 찾는 중이에요` 문구가 깜빡이지 않게 한다.
- RAG/LLM 진행 문구는 실제 AI 답변 생성 중에만 표시한다.
- 이력 로딩 중 메시지 전송과 방 조작 잠금은 유지한다.

## 현재 상태
- `useChatSession`의 `isSending`은 chat mutation, 메시지 저장, 방 생성, 목록·이력 조회를 모두 포함한다.
- `ChatMessages`는 `isSending`이 true이면 provider와 무관하게 RAG부터 시작하는 상태 문구를 표시한다.
- 방 전환 시 짧은 message query가 `isSending`을 켰다가 꺼서 첫 RAG 문구가 깜빡인다.

## 범위
- `useChatSession`에서 상호작용 잠금 상태와 실제 AI 생성 상태를 분리한다.
- ChatWidget과 `/assistant`가 AI 생성 상태만 메시지 진행 표시기에 전달하게 한다.
- 상태 분리 회귀 테스트를 추가한다.
- backend/API/DB/env 계약은 변경하지 않는다.

## 설계
- `isSending`: 중복 전송과 상태 경합 방지를 위한 기존 통합 잠금 상태를 유지한다.
- `isGenerating`: `chatMutation.isPending`만 나타내는 표시 전용 상태로 추가한다.
- `ChatMessages`와 `AssistantStatusIndicator`는 `isGenerating`만 사용한다.
- 방 이력 조회 중에는 현재 UI를 유지하고 별도의 순간 로딩 문구를 만들지 않는다.

## 실행 단계
- [x] hook에 `isGenerating`을 추가하고 테스트한다.
- [x] ChatWidget/ChatPage/ChatMessages 전달 계약을 분리한다.
- [x] 전체 frontend 테스트, lint, build, UI·경계 감사를 실행한다.

## 검증
- `npm --prefix apps/web run test:run`
- `npm --prefix apps/web run lint`
- `npm --prefix apps/web run build -- --outDir <temporary-directory>`
- `npm run agent:audit:ui`
- `npm run agent:audit:web-boundary`
- `git diff --check`

## 위험과 대응
- 위험: 이력 로딩 중 입력이 활성화되어 불완전한 history로 질문을 보낼 수 있다.
- 대응: 입력 disabled와 send guard는 통합 `isSending`을 계속 사용한다.
- 위험: 메시지 저장 단계에서 진행 표시가 잠시 사라질 수 있다.
- 대응: user 저장 후 실제 model mutation이 시작될 때부터 모델 진행 문구를 표시하고 답변 수신 시 종료한다.

## 진행 기록
- 2026-08-11: 방 이동 message query가 RAG 문구를 켜는 상태 혼합 원인을 확인했다.
- 2026-08-11: 통합 잠금 `isSending`은 유지하고 표시 전용 `isGenerating` 전달 경로를 추가했다.
- 2026-08-11: frontend 89개 테스트, lint, production build, UI·frontend 경계 감사를 통과했다.
