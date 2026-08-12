# ExecPlan: Assistant 대화방 전환 스크롤 고정

## 목표
- Assistant 대화 목록에서 다른 대화방으로 이동할 때 과거 메시지부터 아래로 내려가는 애니메이션을 없앤다.
- 전환한 대화방의 최신 메시지가 즉시 보이도록 스크롤 위치를 항상 하단에 둔다.

## 현재 상태
- `ChatMessages`는 메시지 변경 시 생성 중이 아니면 `smooth` 방식으로 하단에 이동한다.
- 이전 대화방에서 위쪽을 읽던 상태가 새 대화방에도 남으면 자동 하단 이동이 생략될 수 있다.
- `ChatMessages`는 전체 페이지와 위젯 패널 두 곳에서 사용된다.

## 범위
- `ChatMessages`에 대화방 식별자를 전달하고 전환 시 스크롤 상태를 초기화한다.
- 자동 하단 이동을 즉시 이동 방식으로 변경하고 회귀 테스트를 추가한다.
- 메시지 조회, 생성, 이전 메시지 불러오기 API와 데이터 계약은 변경하지 않는다.

## 설계
- 활성 대화방 ID를 `conversationKey`로 `ChatMessages`에 전달한다.
- 대화방 키 변경을 layout effect에서 감지해 브라우저가 화면을 그리기 전에 스크롤을 하단으로 맞춘다.
- 메시지 추가에 따른 자동 이동은 `auto`로 처리하되, 사용자가 누르는 최신 답변 이동 버튼은 기존 `smooth` 동작을 유지한다.
- 이전 메시지 불러오기의 스크롤 위치 보존 로직은 유지하고, 대화방 전환 시 이전 요청의 anchor만 무효화한다.
- public facade, migration, env, auth 계약에는 영향이 없다.

## 실행 단계
- [x] 대화방 전환 시 스크롤 상태 초기화 및 즉시 하단 이동 구현
- [x] 전체 페이지와 위젯 패널에서 활성 대화방 키 전달
- [x] 대화방 전환 및 자동 이동 회귀 테스트 추가
- [x] frontend 테스트, lint, UI audit 실행

## 검증
- `npm --prefix apps/web test -- --run src/features/assistant/components/ChatMessages.test.jsx`
- `npm --prefix apps/web run lint`
- `npm run agent:audit:ui`
- `git diff --check`

## 위험과 대응
- 위험: 이전 메시지를 불러올 때 유지해야 하는 읽던 위치까지 하단으로 이동할 수 있다.
- 대응: 대화방 키가 바뀐 경우에만 전환 초기화를 실행하고 기존 scroll anchor 보정 분기는 유지한다.
- 위험: 이전 대화방에서 진행 중인 과거 이력 요청이 새 대화방 스크롤에 영향을 줄 수 있다.
- 대응: 대화방 전환 시 요청 식별자를 갱신하고 저장된 scroll anchor를 제거한다.

## 진행 기록
- 2026-08-12: 현재 자동 스크롤과 대화방 전환 호출부를 확인하고 구현 범위를 확정했다.
- 2026-08-12: 대화방 전환 전용 layout effect와 비애니메이션 자동 스크롤을 구현했다.
- 2026-08-12: ChatMessages 테스트 13개, frontend lint, UI audit, diff 검사를 모두 통과했다.
