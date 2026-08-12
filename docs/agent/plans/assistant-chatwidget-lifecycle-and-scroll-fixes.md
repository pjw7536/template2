# ExecPlan: ChatWidget 생명주기와 스크롤 개선

## 목표
- 사용자 전환·Widget 언마운트 뒤 도착한 이전 요청이 현재 화면을 변경하지 않게 한다.
- 대화 초기화와 메시지 전송이 동시에 실행되지 않게 한다.
- 이전 메시지를 추가로 불러온 뒤 첫 페이지가 재조회되어도 기존 페이지를 유지한다.
- Assistant 전체 페이지에서는 숨겨진 Widget session을 만들지 않는다.
- 스트리밍 중 사용자의 스크롤 위치를 존중하고 접근 가능한 상태 안내를 제공한다.

## 현재 상태
- `useChatSession`의 비동기 작업은 시작 당시 user/session이 여전히 유효한지 확인하지 않는다.
- `clearMutation`은 전송 잠금에 포함되지 않아 초기화 DELETE와 메시지 POST가 겹칠 수 있다.
- 이전 메시지는 local state에만 병합되고 첫 페이지 query refetch가 전체 local 목록을 교체한다.
- `/assistant`에서도 `ChatWidget`이 session hook을 실행한 뒤 `null`을 반환한다.
- `ChatMessages`는 모든 stream delta마다 smooth scroll을 실행한다.

## 범위
- 수정: Assistant session hook과 회귀 테스트, Widget route/lifecycle, 메시지 스크롤, 오류·검색 접근성.
- 제외: backend API, DB schema/migration, auth/permission, public facade, 외부 URL.

## 설계
- session epoch와 mount 상태를 ref로 관리하고 모든 장기 비동기 결과를 반영하기 전에 유효성을 확인한다.
- unmount/user 변경 시 generation을 abort/abandon하고 pending 작업 ref를 무효화한다.
- reset Promise를 동기적으로 점유해 전송과 중복 reset을 차단한다.
- 추가로 불러온 메시지의 older prefix와 pagination cursor를 보존해 첫 페이지 refetch와 병합한다.
- 라우터와 `ChatWidget` wrapper 양쪽에서 Assistant 전체 페이지의 session mount를 차단한다.
- stream delta를 animation frame 단위로 모으고, 하단 근처에 있을 때만 최신 답변을 추적한다.

## 실행 단계
- [x] session epoch·unmount cleanup과 reset lock 구현
- [x] 이전 메시지 page 병합과 cache 동기화 구현
- [x] Assistant route에서 숨겨진 Widget session 제거
- [x] 조건부 자동 스크롤과 접근성 상태 보완
- [x] 회귀 테스트와 frontend 전체 검증

## 검증
- `npm --prefix apps/web run test:run -- src/features/assistant`
- `npm --prefix apps/web run test:run`
- `npm --prefix apps/web run lint`
- 임시 출력 경로 production build
- `scripts/agent/check_frontend_boundaries.sh`
- `scripts/agent/check_ui_consistency.sh`
- `git diff --check`

## 위험과 대응
- 위험: stale 결과 차단이 generation lease 정리를 누락할 수 있다.
- 대응: 화면 반영과 서버 generation 정리를 분리하고 ref가 같은 generation일 때만 local ref를 해제한다.
- 위험: 첫 페이지 병합이 현재 branch에서 제외된 메시지를 되살릴 수 있다.
- 대응: 첫 페이지와 처음 겹치는 메시지 앞의 older prefix만 보존하고 이후 tail은 server 결과로 교체한다.
- 위험: 자동 스크롤 조건 변경으로 새 답변을 놓칠 수 있다.
- 대응: 하단 이탈 시 `최신 답변 보기` action을 표시한다.

## 진행 기록
- 2026-08-12: 추가 리뷰 여섯 항목을 frontend 범위에서 순서대로 개선하기로 확정했다.
- 2026-08-12: session epoch·reset mutex·과거 메시지 prefix 보존·Assistant route mount 차단을 구현했다.
- 2026-08-12: stream delta를 animation frame 단위로 묶고 하단 이탈 시 최신 답변 이동 action과 접근성 label을 추가했다.
- 2026-08-12: 핵심 회귀 테스트 36개와 `git diff --check`가 통과했다.
- 2026-08-12: Assistant 테스트 71개와 frontend 전체 테스트 146개, ESLint, production build, frontend boundary audit, UI consistency audit가 모두 통과했다. build에는 기존 대용량 chunk 경고만 남았다.
