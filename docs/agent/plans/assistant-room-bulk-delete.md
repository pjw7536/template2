# ExecPlan: Assistant 대화방 다중 삭제

## 목표
- 대화방 목록에서 선택 모드로 전환해 현재 불러온 방을 전체 선택하고 한 번의 확인으로 삭제한다.
- 최초 `무엇을 도와드릴까요?` 인사 메시지에는 복사 버튼을 표시하지 않는다.

## 현재 상태
- `RoomList`는 대화방별 단건 삭제 확인창과 검색·cursor 추가 조회를 제공한다.
- `useChatSession.removeRoom`은 기존 본인 소유 대화방 DELETE API를 호출한 뒤 frontend 상태를 갱신한다.
- 답변 생성 중인 방은 기존 단건 삭제가 금지되어 있다.

## 범위
- 수정: Assistant 대화방 선택 UI, 다중 삭제 세션 처리, ChatWidget·전체 화면 연결, 인사 메시지 action, 테스트·문서.
- 제외: backend bulk endpoint, DB/migration, 권한 정책, 보관/검색 계약 변경.

## 설계
- `RoomList`가 현재 표시된 삭제 가능 방의 선택 상태를 소유한다.
- 전체 선택은 현재 검색·보관 필터에서 이미 불러온 방을 대상으로 하고 생성 중인 방은 제외한다.
- 확인창은 선택 개수와 복구 불가 안내를 표시하고 삭제 중 중복 제출을 막는다.
- `useChatSession.removeRooms`는 기존 단건 DELETE를 호출하고 성공 ID를 한 번에 React/React Query 상태에서 제거한다.
- 일부 요청이 실패하면 성공 항목은 유지 삭제하고 실패 개수를 공용 오류 배너에 표시한다.
- 인사 메시지는 기존 `isGreeting` 판정을 재사용해 전체 action bar를 숨긴다.

## 실행 단계
- [x] `removeRooms` 상태 갱신과 부분 실패 처리를 구현한다.
- [x] `RoomList` 선택 모드·전체 선택·확인창을 구현한다.
- [x] ChatWidget과 전체 Assistant 화면에 다중 삭제를 연결한다.
- [x] 최초 인사 메시지의 복사 action을 제거한다.
- [x] frontend 테스트·lint·build·경계/UI 감사를 실행하고 문서를 갱신한다.

## 검증
- `npm --prefix apps/web run test:run -- src/features/assistant`
- `npm run web:lint`
- 임시 경로 production build
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- `git diff --check`

## 위험과 대응
- 위험: 단건 삭제를 반복하며 stale state로 일부 방이 다시 나타날 수 있다.
- 대응: 성공 ID 집합을 계산한 뒤 목록과 메시지 cache를 한 번에 갱신한다.
- 위험: 생성 중 방을 함께 삭제하면 generation 상태가 깨질 수 있다.
- 대응: UI와 세션 함수 양쪽에서 현재 generation 방을 제외한다.
- 위험: 일부 DELETE만 실패할 수 있다.
- 대응: 성공 항목은 제거하고 실패 항목은 선택 상태에 남겨 재시도할 수 있게 한다.

## 진행 기록
- 2026-08-11: 기존 단건 API를 유지하고 현재 불러온 목록 기준 전체 선택으로 구현하기로 결정했다.
- 2026-08-11: 다중 삭제·부분 실패 상태 갱신, 선택 UI, 최초 인사 action 제거를 구현하고 대상 테스트 19개를 통과했다.
- 2026-08-11: 대화방 portal 메뉴가 열린 상태의 바깥 클릭은 메뉴만 닫고 ChatWidget은 유지하도록 outside-click 조건을 보완했다.
- 2026-08-11: frontend 전체 112개 테스트, lint, 임시 경로 production build, frontend boundary/UI audit, diff check를 통과했다.
