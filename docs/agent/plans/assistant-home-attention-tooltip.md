# ExecPlan: 포털 홈 ChatWidget 안내 문구 반복 표시

## 목표
- 사용자가 포털 홈(`/`)에 진입할 때마다 ChatWidget 아이콘 상단에 `무엇이든 물어보세요` 안내 문구를 표시한다.

## 현재 상태
- `useAttentionTooltip`은 `sessionStorage`를 기준으로 세션당 한 번만 표시한다.
- `ChatWidget`은 현재 경로를 알고 있지만 훅에는 Assistant 페이지 여부만 전달한다.

## 범위
- ChatWidget의 홈 경로 판별, 안내 문구 훅의 표시 조건, 관련 훅 테스트를 수정한다.
- 문구, 타이핑 속도, 표시 시간, ChatWidget 권한 조건과 스타일은 변경하지 않는다.

## 설계
- `ChatWidget`이 현재 경로가 `/`인지 판별해 훅에 전달한다.
- 훅은 홈 진입 시 표시 요청 상태를 만들고, 홈 이탈 시 초기화하여 다음 진입을 허용한다.
- `sessionStorage` 기반 세션당 1회 제한은 제거한다.
- public facade, API, DB, auth, migration, env 계약에는 영향이 없다.

## 실행 단계
- [x] 홈 진입 기반으로 안내 문구 훅을 변경한다.
- [x] ChatWidget에서 홈 여부를 훅에 전달한다.
- [x] StrictMode, 홈 이탈·재진입, 홈 외 경로 동작을 테스트한다.

## 검증
- `npm run test:run -- src/features/assistant/hooks/useAttentionTooltip.test.jsx src/features/assistant/components/ChatWidget.test.jsx`
- `npm run agent:audit:ui`
- `npm exec eslint -- src/features/assistant/hooks/useAttentionTooltip.js src/features/assistant/hooks/useAttentionTooltip.test.jsx src/features/assistant/components/ChatWidget.jsx`
- 기대 결과: 관련 테스트와 UI audit가 통과한다.

## 위험과 대응
- 위험: React StrictMode에서 effect cleanup으로 타이핑 타이머가 중단될 수 있다.
- 대응: 홈 진입 감지와 타이머 실행 effect를 분리하고 StrictMode 테스트를 유지한다.
- 위험: 홈 화면의 단순 재렌더링마다 문구가 반복될 수 있다.
- 대응: 홈 이탈 시에만 표시 요청 상태를 초기화한다.

## 진행 기록
- 2026-08-12: 홈 진입마다 표시하는 요구사항과 검증 범위를 확정했다.
- 2026-08-12: 세션 플래그 의존성을 제거하고 홈 진입 상태 기반 구현과 테스트를 추가했다.
- 2026-08-12: 첫 검증에서 확인된 기존 Assistant 페이지 숨김 변수 누락을 복원했다.
- 2026-08-12: 관련 테스트 5개, UI consistency audit, 변경 파일 ESLint와 `git diff --check`가 모두 통과했다.
