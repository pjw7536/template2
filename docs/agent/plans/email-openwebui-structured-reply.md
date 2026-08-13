# ExecPlan: Email OpenWebUI 구조화 응답 호환성

## 목표
- OpenWebUI Chat Completions의 `message.content`가 Email 출처 `segments`를 제공하면 최상위 `answer`가 비어도 Turn이 실패하지 않도록 한다.
- Prompt와 parser가 동일한 조건부 `answer` 계약을 사용하도록 정렬한다.

## 현재 상태
- OpenWebUI 공식 API는 `/api/chat/completions`를 OpenAI-compatible Chat Completions endpoint로 제공하고, 응답 본문은 assistant `message.content` 문자열이다.
- OpenWebUI 공식 소스는 Chat Completions 요청 body를 선택된 upstream model로 전달하며, Email의 `answer`/`segments` 내부 JSON 계약을 검증하지 않는다.
- 현재 Email prompt는 `segments`가 있으면 최상위 `answer`를 표시하지 않는다고 안내하지만, parser는 `segments` 유무와 무관하게 비어 있지 않은 `answer`를 필수로 검증했다.
- 실패 traceback은 OpenWebUI 호출과 JSON decode 이후 `answer` 검증에서 중단된 것을 보여준다.

## 범위
- `apps/api/api/assistant/services/reply.py`의 조건부 `answer` 검증을 수정한다.
- `apps/api/api/assistant/services/llm.py`의 Email 출력 규칙을 parser와 동일하게 정렬한다.
- `apps/api/api/assistant/tests.py`에 정상·거부 회귀 테스트를 추가한다.
- 새 API, DB, migration, auth/permission, env 계약은 추가하지 않는다.

## 설계
- `segments` 배열을 먼저 엄격하게 검증한다.
- 유효한 `segments`가 1개 이상이면 표시 답변은 segment로 구성되므로 최상위 `answer`가 문자열이 아니어도 Turn을 실패시키지 않는다.
- `segments` 배열이 비면 최상위 `answer`를 반드시 필요로 한다.
- `response_format`은 추가하지 않는다. 이번 실패 응답은 이미 JSON decode를 통과했고, OpenWebUI 뒤의 provider/model이 JSON Schema를 지원하는지는 현재 설정에서 보장되지 않는다.
- dev dummy는 기존 `answer` + 빈 `segments` 응답을 계속 사용하므로 변경하지 않는다.

## 실행 단계
- [x] OpenWebUI 공식 API 문서와 공식 router 소스를 확인한다.
- [x] Email prompt와 parser 계약을 정렬한다.
- [x] 유효한 segments + 빈/missing answer 및 전체 빈 응답 테스트를 검증한다.
- [x] dev dummy OpenAI-compatible SSE 흐름과 Assistant 전체 테스트를 검증한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.assistant.tests.AssistantChatServiceSourceFilteringTests --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.assistant --keepdb`
- `git diff --check`

## 위험과 대응
- 위험: 출처가 없는 빈 응답까지 정상으로 오판할 수 있다.
- 대응: `segments` 및 최상위 `answer`가 모두 비면 기존 예외를 유지한다.
- 위험: provider별 `response_format` 지원 차이로 요청 자체가 실패할 수 있다.
- 대응: 선택된 upstream model capability가 확정되지 않은 상태에서 `response_format`을 새로 강제하지 않는다.

## 진행 기록
- 2026-08-13: OpenWebUI가 보장하는 것은 Chat Completions 응답 계약이며, Email 내부 JSON field는 앱이 검증해야 하는 계약으로 확정했다.
- 2026-08-13: 실패한 응답은 JSON decode를 통과했으므로 `response_format` 부재가 직접 원인이 아님을 확정했다.
- 2026-08-13: Email 대상 테스트 9개, Assistant 전체 테스트 48개, dev dummy SSE 실제 호출과 `git diff --check`가 통과했다.
