# ExecPlan: ChatWidget 재리뷰 결함 수정

## 목표
- 첫 전송이나 새 대화 action이 중복 실행되어 빈 대화방을 남기지 않게 한다.
- 생성·이름 변경·고정·자동 제목 결과를 conversation React Query cache와 즉시 동기화한다.
- 생성 직전 background conversation query가 새 방을 덮어쓰지 않게 한다.
- `StreamingText` 구현과 1초 테스트 계약을 일치시킨다.

## 현재 상태
- `sendMessage`의 전송 잠금은 방 생성과 generation 획득 뒤에 설정된다.
- `createRoom`은 local rooms와 message cache만 갱신하고 conversation cache는 갱신하지 않는다.
- 이름 변경·고정·자동 제목은 local state만 변경해 cache scope 전환 시 이전 값이 복원될 수 있다.
- `StreamingText`는 300ms 후 시작하지만 테스트는 1초를 요구한다.

## 범위
- 수정: Assistant frontend session hook, 스트리밍 상수, 관련 hook/component 테스트.
- 제외: backend API, DB schema/migration, 인증·권한, public facade, UI layout.

## 설계
- `sendMessage` 진입 즉시 동기 promise ref를 점유하고 준비 상태를 `isSending`에 포함한다.
- `createRoom`도 promise를 coalesce해 중복 POST를 방지한다.
- 방 생성 전 conversation query를 취소하고, 성공 결과를 active/archived cache에 공통 updater로 반영한다.
- 생성·이름 변경·고정·자동 제목이 동일한 cache 동기화 함수를 사용한다.
- 스트리밍 시작 지연은 테스트 계약인 1초로 통일한다.

## 실행 단계
- [x] 전송·대화방 생성 reentrant lock 구현
- [x] conversation cache 공통 updater와 mutation 동기화 구현
- [x] 동시 전송·cache scope 전환 회귀 테스트 추가
- [x] 스트리밍 계약 정합화
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
- 위험: cache updater가 active/archived scope에 방을 동시에 노출할 수 있다.
- 대응: normalized `archived` 상태에 따라 한쪽에만 포함하고 반대쪽에서는 제거한다.
- 위험: 중복 전송 차단이 정상 재시도까지 막을 수 있다.
- 대응: promise 종료 시 동일 ref만 해제하고 실패·취소 후 즉시 재시도를 허용한다.

## 진행 기록
- 2026-08-12: 재리뷰 findings 네 건을 frontend 범위에서 수정하기로 확정했다.
- 2026-08-12: 첫 전송 잠금과 대화방 생성 Promise 공유로 재진입 시 중복 대화방이 생성되지 않도록 수정했다.
- 2026-08-12: 생성·제목 생성·이름 변경·고정·보관·최근 사용 시 대화방 목록 cache를 활성/보관 범위에 맞게 동기화했다.
- 2026-08-12: 스트리밍 시작 지연을 기존 테스트 계약인 1초로 복원하고 관련 회귀 테스트를 추가했다.
- 2026-08-12: frontend 테스트 139개, ESLint, production build, frontend boundary audit, UI consistency audit, `git diff --check`가 모두 통과했다. build에는 기존 대용량 chunk 경고만 남았다.
