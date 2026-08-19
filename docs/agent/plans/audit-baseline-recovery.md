# ExecPlan: 감사 기준선 복구

## 목표
- 기준선 숫자를 올리지 않고 Drone selector/test 증가분을 책임별 파일로 분리해 `agent:audit:hotspots`를 복구한다.
- 공개 symbol, test discovery 수, API/DB/권한 동작을 바꾸지 않는다.

## 현재 상태
- 구현 전 `apps/api/api/drone/selectors.py`는 1,973줄로 1,893줄 기준선을 80줄 초과했다.
- 구현 전 `apps/api/api/drone/tests.py`는 9,630줄로 9,571줄 기준선을 59줄 초과했다.
- 분리 후 두 파일은 각각 1,893줄과 9,535줄이며 기존 기준선을 올리지 않고 hotspot 감사를 통과한다.
- git history상 두 초과분은 2026-08-15 Assistant ESOP snapshot 필터/응답과 회귀 테스트 두 건에서 발생했다.

## 범위
- 수정: Drone selector/test 파일 구조와 snapshot 입력·응답 직렬화 책임 분리, hotspot baseline의 obsolete row 검사.
- 제외: Drone 업무 규칙, model/migration, view/API payload, Spider·Teamstaff.

## 설계
- `selectors.py`에는 ORM filter/aggregation만 남기고 Assistant snapshot의 순수 옵션 검증·시간 범위 계산과 row→camelCase payload 변환을 `serializers.py`의 명시적 함수로 이동한다.
- `get_line_dashboard_assistant_snapshot` 공개 symbol과 `api.drone.selectors.timezone.now` patch target은 유지한다.
- 2026-08-15 추가된 snapshot 회귀 테스트 두 건을 독립 `test_assistant_snapshot.py`로 이동한다. 기존 `DroneSelectorCaseInsensitiveTests`의 다른 테스트와 helper는 이동하지 않는다.
- 새 테스트 파일은 자체 fixture만 소유하며 기존 대형 `tests.py`의 private helper를 import하지 않는다.
- schema/API/env/auth 변화와 migration은 없다.

## 실행 단계
- [x] git history로 증가한 selector/test 범위를 식별한다.
- [x] snapshot 옵션·payload 직렬화를 `serializers.py`로 이동하고 공개 selector/patch target을 유지한다.
- [x] 두 신규 test method를 독립 test module로 이동하고 동일 test 수를 확인한다.
- [x] obsolete baseline row를 검사한다. 두 대형 파일 모두 기본 임계치보다 커 기존 row를 유지한다.
- [x] Drone test와 전체 정적 감사를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.drone`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:hotspots`
- `git diff --check`
- 기대 결과: Drone discovered test 수 불변, hotspot 기준 상향 0건, 감사 전체 통과.

## 위험과 대응
- 위험: 직렬화 이동으로 field 누락·순서·datetime 표현이 달라진다.
- 대응: 기존 payload assertion을 독립 test module에서 그대로 유지한다.
- 위험: test module 분리로 공통 helper에 의존하거나 discovery 수가 달라진다.
- 대응: fixture를 독립 구성하고 이동 전후 두 test가 각각 한 번씩 실행되는지 확인한다.

## 의존성과 복구
- 상위 계약: [마스터 계획](repository-refactor-master-2026-08.md). 후행 계획은 Platform Common이며 이 단계의 Drone facade를 Line Dashboard 계획이 재사용한다.
- 복구: schema/data 변화가 없으므로 serializer helper를 selector에 되돌리고 두 test를 `tests.py`에 복원한다. baseline 수치는 변경하지 않는다.

## 진행 기록
- 2026-08-18: 두 증가 hotspot과 정확한 초과 줄 수를 재현했다.
- 2026-08-18: git history로 증가분이 Assistant snapshot과 test 두 건임을 확인해 전체 package 전환 대신 해당 책임만 분리하도록 계획을 다시 동결했다.
- 2026-08-18: selector 1,893줄, 기존 tests 9,535줄로 기준선 상향 없이 복구했다. 독립 snapshot 테스트 2건과 Drone 전체 297건, migration drift, 전체 agent audit, diff 검사를 통과해 계획을 완료했다.
