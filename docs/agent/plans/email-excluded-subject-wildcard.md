# ExecPlan: 메일 제목 제외 wildcard 지원

## 목표
- `EMAIL_EXCLUDED_SUBJECT_PREFIXES=[drone_sop*],[test]`처럼 설정했을 때 `*`를 0글자 이상의 wildcard로 해석합니다.
- 기존 literal prefix 규칙은 호환성을 유지합니다.

## 현재 상태
- `apps/api/api/emails/services/ingest.py`는 설정값을 `str.startswith()`로만 비교하므로 `*`를 문자 그대로 처리합니다.
- `env/api.common.env`의 현재 Drone SOP 제외값은 닫는 대괄호가 누락되어 버전 태그를 의도대로 표현하지 못합니다.
- 설정값은 `apps/api/config/settings.py`에서 쉼표로 분리해 소문자로 정규화합니다.

## 범위
- 메일 수집의 제목 제외 matcher, 기본 설정값, 공용 env 예시, 설정 문서, 단위 테스트를 수정합니다.
- POP3 연결, 메일 저장, OCR 및 다른 도메인의 필터 동작은 수정하지 않습니다.

## 설계
- 각 패턴을 시작점이 고정된 정규식으로 한 번만 컴파일합니다.
- `*`만 wildcard로 변환하고 대괄호를 포함한 나머지 문자는 literal로 escape합니다.
- 제목은 기존처럼 양끝 공백 제거와 소문자 변환 후 비교합니다.
- DB migration과 auth/API contract 변경은 없습니다. env 값의 해석 규칙만 확장됩니다.

## 실행 단계
- [x] wildcard matcher와 기본 패턴을 구현합니다.
- [x] 공용 env와 설정 문서에 `[drone_sop*],[test]` 규칙을 반영합니다.
- [x] wildcard, literal, 대소문자, 비일치 사례를 검증하는 테스트를 추가합니다.

## 검증
- `docker compose -f docker-compose.dev.yml run --rm --no-deps --entrypoint python api manage.py test api.emails.tests.EmailExcludedSubjectPatternTests`
- `docker compose -f docker-compose.dev.yml run --rm --no-deps --entrypoint python api manage.py check`
- `git diff --check`
- 기대 결과: 모든 명령이 성공하고 `[drone_sop]`, `[drone_sop_v1]`, `[drone_sop_v2]`는 제외되며 다른 prefix는 제외되지 않습니다.

## 위험과 대응
- 위험: 정규식 메타문자가 의도치 않게 활성화될 수 있습니다.
- 대응: `*`로 나누어진 각 조각을 `re.escape()` 처리하고 테스트로 대괄호의 literal 동작을 검증합니다.
- 위험: module import 시 컴파일된 설정값 때문에 `override_settings`가 테스트 중 즉시 반영되지 않을 수 있습니다.
- 대응: matcher 컴파일 함수를 직접 검증하고 실제 제외 함수에는 명시적으로 컴파일된 matcher를 patch합니다.

## 진행 기록
- 2026-08-21: `*`는 0글자 이상을 의미하고 제목 시작점에서만 비교하는 것으로 설계를 확정했습니다.
- 2026-08-21: matcher, 기본 env, 설정 문서와 회귀 테스트를 구현했습니다.
- 2026-08-21: 대상 테스트 4건, Django system check, `git diff --check`가 모두 통과했습니다.
- 2026-08-21: dev `api`가 실행 중이지 않아 일회성 컨테이너를 사용했습니다. 첫 실행은 dev entrypoint가 seed와 서버를 시작해 중단·정리했고, 이후 `--entrypoint python`으로 검증했습니다.
