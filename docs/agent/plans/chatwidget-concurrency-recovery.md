# ExecPlan: ChatWidget 동시성 및 복구 안정화

## 목표
- ChatWidget의 세션 전환, 저장 실패, 목록 조회, 페이지네이션, 연속 조작, 스크롤 복구 경합을 제거한다.

## 현재 상태
- `useChatSession.js`는 세션 epoch로 이전 요청의 데이터 반영을 막지만 React Query mutation의 pending 상태는 세션과 분리되어 있지 않다.
- `RoomList.jsx`는 최초 마운트에도 빈 검색 요청을 실행한다.
- 페이지네이션과 일부 메타데이터 변경은 동일 시점의 중복 요청 또는 응답 역전 가능성이 있다.
- `ChatMessages.jsx`의 이전 메시지 스크롤 기준값은 요청 실패 시 남을 수 있다.

## 범위
- 수정: `apps/web/src/features/assistant/hooks/useChatSession.js`
- 수정: `apps/web/src/features/assistant/components/RoomList.jsx`
- 수정: `apps/web/src/features/assistant/components/ChatMessages.jsx`
- 수정: `apps/web/src/features/assistant/components/ChatErrorBanner.jsx` 및 호출부
- 수정: 관련 Assistant 테스트
- 제외: backend/API 계약, DB, auth, 다른 feature

## 설계
- 세션별 로딩 상태와 진행 Promise를 로컬 state/ref로 관리하고 이전 세션 완료가 새 세션 상태를 바꾸지 않게 한다.
- 저장 실패 복구 상태는 일반 오류와 분리해 재시도 또는 제거 전까지 표시한다.
- 최초의 변경되지 않은 빈 검색을 생략하고 페이지 요청은 Promise ref로 합친다.
- 메시지 평가와 대화방 메타데이터는 대상별 최신 요청만 UI에 반영한다.
- 이전 메시지 로딩 결과로 실제 메시지가 추가된 경우에만 스크롤 anchor를 복구한다.
- public facade, API request/response, migration/env/auth 계약은 변경하지 않는다.

## 실행 단계
- [x] 세션별 진행 상태와 저장 실패 복구 상태를 안정화한다.
- [x] 검색 및 페이지네이션 중복 요청을 차단한다.
- [x] 연속 메타데이터 조작의 최신 요청 우선 처리를 추가한다.
- [x] 이전 메시지 스크롤 anchor의 성공/실패 처리를 보강한다.
- [x] 관련 회귀 테스트를 추가하고 전체 Assistant 검증을 실행한다.

## 검증
- `npm test -- --run src/features/assistant`
- `npm run lint -- src/features/assistant`
- `scripts/agent/check_frontend_boundaries.sh`
- `scripts/agent/check_ui_consistency.sh`

## 위험과 대응
- 위험: 로컬 pending 상태가 실제 요청 완료와 어긋날 수 있다.
- 대응: 각 Promise를 ref에 저장하고 동일 Promise의 `finally`에서만 상태를 해제한다.
- 위험: 오래된 응답을 무시하면서 서버와 로컬 상태가 잠시 달라질 수 있다.
- 대응: 최신 요청만 반영하고 기존 React Query cache 갱신 경로를 유지한다.

## 진행 기록
- 2026-08-12: 코드리뷰에서 확인한 6개 문제를 기존 계약 변경 없이 수정하기로 결정했다.
- 2026-08-12: 세션별 pending 상태, 복구 배너, 중복 페이지 요청, 순차 작업 queue, 스크롤 anchor 처리를 구현했다.
- 2026-08-12: Assistant 테스트 74개, ESLint, frontend boundary audit, UI consistency audit, 임시 경로 production build를 통과했다.
- 2026-08-12: 기본 `dist` 빌드는 기존 root 소유 파일 삭제 권한 문제로 중단되며, 코드 검증은 임시 출력 경로로 완료했다.
