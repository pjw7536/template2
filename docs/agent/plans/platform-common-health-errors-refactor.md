# ExecPlan: Platform Common·Health·Errors 단일화

## 목표
- settings/env parser, request helper, middleware, 외부 HTTP/storage adapter와 오류 계약의 중복을 제거한다.
- `/api/v1/health/`와 frontend route error 화면의 사용자 동작을 유지한다.

## 현재 상태
- `config/settings.py`가 env fallback, 외부 URL, feature 설정을 한 파일에서 처리한다.
- `api.common.services`에 request, DB, storage, mail, messenger, cancellation, stream helper가 있으나 feature별 직접 `requests` 호출과 오류 shape가 남아 있다.
- `RACB_REPORT_BASE_URL`은 settings에 URL 기본값이 하드코딩돼 있고 `PUBLIC_API_BASE_URL`은 두 env key를 fallback한다.
- frontend `errors` feature는 wildcard route와 route error page를 제공한다.

## 범위
- 수정: `apps/api/config/settings.py`, `api.common`, `api.health`, `apps/web/src/features/errors`, 공통 HTTP client 소비처와 설정 문서/env.
- 유지: 외부 provider별 payload, timeout/cancel fallback, health URL/status 의미.
- 제외: Spider·Teamstaff 설정과 코드. 해당 설정은 그대로 둔다.

## 설계
- 비-Spider settings parser는 잘못된 bool/int/JSON 값을 조용히 default로 바꾸지 않고 시작 시 `ImproperlyConfigured`를 발생시킨다. 선택 문자열 env가 비어 있어 기능을 끄는 경우만 허용한다. 제외 범위인 Spider 설정은 기존 parser 호출과 동작을 유지한다.
- `PUBLIC_API_BASE_URL`만 canonical key로 사용하고 `DJANGO_PUBLIC_API_BASE_URL` fallback을 제거한다.
- `RACB_REPORT_BASE_URL`은 빈 기본값의 필수 기능 env로 전환하며 Observer RACB URL은 값이 있을 때만 제공한다.
- `request_helpers.py`가 JSON object parsing, camelCase field validation, 공통 error body를 소유한다.
- `cancellation.py`와 공통 HTTP adapter가 connect/read timeout과 client disconnect를 구분한다. Mail/Messenger/RAG/OpenWebUI의 provider payload 조립은 각 소유 domain에 남긴다.
- middleware는 인증/접근/활동 기록 순서를 보존한다. 이 단계에서는 middleware와 공용 request/token helper가 직접 생성하는 비-Spider API 오류만 공통 error shape로 반환한다. 업무 feature view/service의 기존 오류는 각 소유 계획에서 소비자와 함께 전환하며, Spider API 응답은 재작성하지 않는다.
- Health는 DB/storage/external probe를 새로 추가하지 않고 process readiness만 반환해 장애 전파를 막는다.
- frontend error page는 route error의 status/code/message를 안전하게 표시하고 raw stack/payload는 노출하지 않는다.
- migration은 없다.

## 실행 단계
- [x] 공통 helper와 feature-local 중복 호출/오류 변환을 characterization한다.
- [x] strict env parser와 canonical setting key를 도입하고 env/Compose/docs를 동기화한다.
- [x] 공통 request/error/HTTP adapter를 적용한다.
- [x] middleware와 Health/Error 화면 회귀 테스트를 보강한다.
- [x] 후행 feature가 사용할 public facade를 명시적으로 고정한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.common api.health`
- `npm run web:test -- --run apps/web/src/features/errors`
- `docker compose -f docker-compose.dev.yml config`
- `npm run agent:audit`
- 오류별 400/401/403/502/504 body snapshot과 health 200 smoke test.

## 위험과 대응
- 위험: strict env parsing이 기존 잘못된 배포값을 즉시 실패시킨다.
- 대응: 배포 전 `docker compose config`와 settings import smoke를 실행하고 configuration 문서에 허용 형식을 기록한다.
- 위험: 공통 adapter가 provider 특화 오류 정보를 잃는다.
- 대응: 내부 cause는 log metadata에 보존하고 공개 body만 표준화한다.

## 의존성과 복구
- 상위 계약: [마스터 계획](repository-refactor-master-2026-08.md). 감사 기준선 다음에 실행하며 이후 모든 API 계획이 공통 request/error/HTTP adapter를 사용한다.
- 복구: migration이 없으므로 consumer별 adapter 전환을 역순으로 되돌린 뒤 strict env key를 복원한다. 배포 env가 canonical key로 이동한 뒤에는 이전 key를 재주입해야 rollback할 수 있다.

## 진행 기록
- 2026-08-18: 다중 public API env fallback과 RACB URL 기본값을 제거 대상으로 확정했다.
- 2026-08-18: 전역 응답 재작성은 제외된 Spider API와 모든 후행 feature를 동시에 변경한다는 사실을 확인했다. 공용 계층 소유 오류만 먼저 전환하고 업무 오류는 각 feature 단계에서 전환하도록 재동결했다.
- 2026-08-18: 비-Spider strict bool/int/JSON parser, canonical `PUBLIC_API_BASE_URL`, 공통 오류 builder, 취소와 connect/read timeout을 구분하는 외부 HTTP adapter를 적용했다. Mail·Messenger·OpenAI stream이 adapter를 사용하고 RACB base URL이 비어 있으면 링크를 숨긴다.
- 2026-08-18: 변경 범위 23개 파일(신규 4개 포함)은 15,473줄에서 16,058줄로 늘었다. 증가는 오류/timeout/제외 범위 회귀 테스트와 공개 계약 코드이며 hotspot 기준선은 올리지 않았다.
- 2026-08-18: backend 전체 1,109개, frontend 전체 185개 테스트와 frontend lint/build, Compose config, Django check/migration drift, 전체 agent audit, diff 검사를 통과해 계획을 완료했다. offsite dummy endpoint 변경은 없고 dev env/Compose 연결은 그대로 유효하다.
