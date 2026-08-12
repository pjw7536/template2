# ExecPlan: Observer OpenWebUI 스트리밍

## 목표
- Observer ChatWidget 분석을 OpenWebUI SSE 스트리밍으로 전환한다.
- 생성 중에는 완성된 분석 블록부터 표시하고, 완료 후 기존 구조화 분석과 근거 링크를 유지한다.

## 현재 상태
- 프론트엔드는 `POST /api/v1/observer/analysis`의 단일 JSON 응답을 기다린다.
- 백엔드는 Observer 로그 문맥을 만든 뒤 OpenWebUI에 `stream: false`로 구조화 JSON을 요청한다.
- 일반 Assistant에는 `meta`, `delta`, `done`, `error` SSE 패턴과 중단 처리가 이미 있다.

## 범위
- Observer 전용 OpenWebUI transport, 분석 service, HTTP view/route를 수정한다.
- Observer 프론트 API와 page assistant sender를 스트림 endpoint로 전환한다.
- 서비스·뷰·프론트 스트림 파서 회귀 테스트를 추가한다.
- 일반 Assistant, DB schema, 권한, env/Compose 계약은 변경하지 않는다.

## 설계
- 기존 `/analysis` JSON endpoint는 호환성을 위해 유지하고 `/analysis/stream`을 추가한다.
- OpenWebUI에는 한 줄당 하나의 분석 블록을 반환하는 NDJSON 계약으로 요청한다.
- 백엔드는 완성된 NDJSON 블록을 SSE `delta`로 전달하고 마지막에 정규화된 기존 payload를 `done`으로 전달한다.
- 프론트는 분석 블록을 Markdown으로 바꿔 `onDelta`에 전달하고, `done` payload로 최종 reply와 context snapshot을 만든다.
- migration, auth, env 변경은 없다.

## 실행 단계
- [x] Observer OpenWebUI streaming transport와 NDJSON 분석 service를 구현한다.
- [x] Observer SSE view와 route를 추가한다.
- [x] 프론트 SSE parser와 ChatWidget sender를 연결한다.
- [x] 백엔드·프론트 회귀 테스트를 추가하고 검증한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.observer`
- `npm run test:run -- src/features/observer` (`apps/web` 기준)
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- 변경 파일 ESLint 및 `git diff --check`

## 위험과 대응
- 위험: raw JSON 조각이 사용자 메시지에 노출될 수 있다.
- 대응: 완성된 NDJSON 객체만 `delta`로 내보내고 프론트에서 표시용 Markdown으로 변환한다.
- 위험: 스트림 중 오류가 HTTP status로 표현되지 않는다.
- 대응: 연결 후 오류는 SSE `error` 이벤트로 전달하고, 연결 전 validation 오류는 기존 JSON status를 유지한다.
- 위험: 중단된 브라우저 연결이 upstream 연결을 남길 수 있다.
- 대응: generator 종료 시 OpenWebUI response/session을 `finally`에서 닫는다.

## 진행 기록
- 2026-08-12: 기존 Assistant SSE 패턴과 Observer 구조화 응답 제약을 확인하고 NDJSON 블록 스트림 설계를 선택했다.
- 2026-08-12: `/analysis/stream` SSE와 frontend parser를 연결했다. Observer backend 74건과 frontend Observer 26건, Assistant session 포함 관련 31건이 통과했다. migration 변경이 없고 backend/frontend/UI audit이 모두 통과했다.
