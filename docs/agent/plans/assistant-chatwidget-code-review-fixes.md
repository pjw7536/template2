# ExecPlan: ChatWidget 코드리뷰 결함 수정

## 목표
- 캐시된 대화방의 background refetch가 전송 중 로컬 메시지를 덮어쓰지 않게 한다.
- 불러온 과거 메시지를 렌더링 상한으로 버리면서 cursor만 전진시키는 문제를 제거한다.
- 다른 방에서 답변 생성 중일 때 수정·재생성을 일관되게 잠근다.
- 삭제한 대화방이 React Query cache나 늦은 검색 응답에서 다시 나타나지 않게 한다.

## 현재 상태
- `useChatSession`은 server query 결과와 optimistic/streaming 메시지를 같은 `messagesByRoom`에 저장한다.
- 캐시가 있는 방의 background refetch는 전송 잠금 대상이 아니며 조회 완료 시 방 메시지를 통째로 교체한다.
- 과거 메시지를 앞에 추가한 뒤 최신 500개만 남겨, 오래된 page가 화면에 반영되지 않아도 cursor는 전진한다.
- 메시지 action은 현재 방의 `isGenerating`만 사용하지만 실제 전송 guard는 사용자 전체 generation을 차단한다.
- 방 삭제는 로컬 목록과 메시지 query만 갱신하고 conversation 목록 cache를 보존한다.

## 범위
- 수정: Assistant frontend session hook, conversation API, ChatMessages와 Widget/Page prop 연결, 관련 테스트.
- 제외: backend API, DB schema/migration, 인증/권한, UI layout 변경.

## 설계
- 메시지 query는 `AbortSignal`을 지원하고, 전송 직전 해당 방 query를 취소한다.
- 방별 pending message ID를 추적하고 pending 상태에서는 local snapshot을 우선해 optimistic/streaming/수정 분기/저장 실패 메시지를 보존한다.
- 과거 page는 ID 기준으로 병합하되 렌더링 500개 절단을 적용하지 않는다. 모델 history 20개 제한은 유지한다.
- `hasActiveGeneration`과 현재 방 표시용 `isGenerating`을 분리하고, 수정·재생성은 전역 generation 상태로 잠근다.
- 삭제 전 conversation query와 수동 검색 응답을 무효화하고, 성공 ID를 active/archived cache에서 즉시 제거한 뒤 재조회한다.

## 실행 단계
- [x] query 취소·메시지 병합·과거 page 보존 구현
- [x] generation action 잠금과 비동기 수정 dialog 처리
- [x] 삭제 cache 정리와 늦은 검색 응답 차단
- [x] hook/component/API 회귀 테스트 추가
- [x] frontend 테스트·lint·build·boundary/UI audit 실행

## 검증
- `npm --prefix apps/web run test:run -- src/features/assistant`
- `npm --prefix apps/web run lint`
- 임시 출력 경로 production build
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- `git diff --check`

## 위험과 대응
- 위험: query 응답 병합이 서버에서 삭제된 메시지를 보존할 수 있다.
- 대응: pending ID 또는 streaming 상태가 명시된 로컬 메시지만 보존하고 저장 완료 후 query를 재동기화한다.
- 위험: 삭제 후 refetch 전에 cursor metadata가 오래될 수 있다.
- 대응: 성공 ID를 즉시 제거한 뒤 목록 query를 invalidate해 서버 cursor를 다시 받는다.
- 위험: 과거 메시지 누적으로 DOM이 커질 수 있다.
- 대응: 페이지는 사용자 요청 시 20개씩만 추가하며, 데이터 유실이 없는 상태를 우선하고 필요 시 별도 virtualization 작업으로 분리한다.

## 진행 기록
- 2026-08-12: 코드리뷰에서 확인한 네 가지 frontend 결함을 API/DB 변경 없이 수정하기로 확정했다.
- 2026-08-12: query 취소와 pending local snapshot 우선 병합을 적용하고, 과거 메시지 500개 절단을 제거했다.
- 2026-08-12: 전역 generation 액션 잠금, 삭제 tombstone/cache 정리, 비동기 수정 dialog 결과 처리를 반영했다.
- 2026-08-12: 전체 frontend 131개 테스트, ESLint, production build, frontend boundary/UI consistency audit, `git diff --check`를 통과했다.
- 2026-08-12: 전체 테스트에서 발견된 인사말 스트리밍 시작 지연 상수와 1초 테스트 계약의 불일치를 1초로 정합화했다.
