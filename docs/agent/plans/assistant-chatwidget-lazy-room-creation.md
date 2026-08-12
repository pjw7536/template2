# ExecPlan: ChatWidget 대화방 지연 생성

## 목표
- 위젯 mount·재mount 또는 마지막 대화방 삭제만으로 서버 대화방이 생성되지 않게 한다.
- 사용자가 새 대화를 명시적으로 누르거나 첫 메시지를 전송할 때만 대화방을 생성한다.
- 대화방이 없을 때는 저장되지 않은 가상 인사말과 빈 목록 상태를 유지한다.

## 현재 상태
- `ChatWidget` 초기화 effect가 위젯의 열림 여부와 무관하게 빈 목록이면 `createRoom("새 대화")`를 호출한다.
- `removeRooms`는 마지막 대화방 삭제 성공 후 `createRoom("새 대화")`를 호출한다.
- `sendMessage`는 활성 대화방이 없을 때 `getOrCreateActiveRoomId`를 통해 대화방을 생성할 수 있다.
- 첫 전송에서 생성된 방도 기존 자동 생성 방과 동일하게 제목 생성 대상이어야 한다.

## 범위
- 수정: Assistant ChatWidget 초기화, session hook의 생성 조건과 관련 frontend 테스트.
- 제외: backend API, DB schema/migration, 인증·권한, 대화방 목록/메시지 응답 계약.

## 설계
- `ChatWidget`의 mount 기반 자동 생성 effect와 전용 ref를 제거한다.
- 마지막 방 삭제 후 자동 생성하지 않고 `rooms=[]`, `activeRoomId=null`을 유지한다.
- `resetConversation`은 활성 방이 없으면 생성하지 않고 종료한다.
- `sendMessage`의 지연 생성 경로는 유지하고, 생성 직후 room ref를 동기화해 제목 생성도 정상 동작하게 한다.
- public facade와 API contract는 변경하지 않는다.

## 실행 단계
- [x] mount·삭제·초기화 자동 생성 경로 제거
- [x] 첫 메시지 지연 생성과 room ref 동기화 보강
- [x] 자동 미생성·첫 전송 생성 회귀 테스트 추가
- [x] frontend 테스트·lint·build·boundary/UI audit 실행

## 검증
- `npm --prefix apps/web run test:run -- src/features/assistant`
- `npm --prefix apps/web run test:run`
- `npm --prefix apps/web run lint`
- 임시 출력 경로 production build
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- `git diff --check`

## 위험과 대응
- 위험: 빈 대화방에서 첫 전송 시 제목 생성이 누락될 수 있다.
- 대응: 방 생성과 동시에 room ref를 갱신하고 제목 생성 호출을 회귀 테스트한다.
- 위험: 활성 방 없이 초기화 action이 방을 생성할 수 있다.
- 대응: `resetConversation`은 유효한 기존 방만 대상으로 제한한다.

## 진행 기록
- 2026-08-12: 사용자가 권장안인 명시적 생성·첫 전송 지연 생성 방식을 확정했다.
- 2026-08-12: mount·마지막 방 삭제·빈 상태 초기화의 자동 생성 경로를 제거했다.
- 2026-08-12: 첫 전송 지연 생성 직후 room ref를 동기화해 자동 제목 생성 흐름을 유지했다.
- 2026-08-12: 관련 회귀 테스트 21개, ESLint, production build, frontend boundary/UI consistency audit, `git diff --check`를 통과했다.
- 2026-08-12: 전체 frontend 135개 중 133개가 통과했으며, 현재 워크트리의 `StreamingText` 시작 지연 300ms와 기존 1초 테스트 계약 불일치로 범위 밖 테스트 2개가 실패했다.
