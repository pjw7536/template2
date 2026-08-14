# ExecPlan: Observer ChatWidget 분석 기간 정합화

## 목표
- Observer ChatWidget이 화면에서 선택 가능한 최대 90일 조회 범위를 별도 31일 오류 없이 분석하게 한다.

## 현재 상태
- Observer 화면은 조회 기간을 최대 90일로 제한한다.
- Assistant Runtime은 Observer 분석 기간을 별도로 최대 31일로 제한해 32일 이상 요청을 거부한다.

## 범위
- Observer backend 공개 계약에 최대 조회 기간을 정의하고 serializer와 Assistant Runtime에서 함께 사용한다.
- 31일 초과 범위와 90일 경계에 대한 Runtime 회귀 테스트를 추가한다.
- Observer 조회 화면, DB schema, auth, env, 외부 OpenWebUI 계약은 변경하지 않는다.

## 설계
- 화면에서 전달한 `from`과 `to`를 기존 방식으로 Asia/Seoul 날짜 경계로 정규화한다.
- 정상 순서의 최대 90일 범위는 분석하고 90일을 넘는 API 요청은 기존 조회 보호 정책에 맞춰 거부한다.
- frontend는 자체 UI 범위 상수를 유지하되 backend 내부의 기간 검증은 Observer 공개 계약 한 곳을 참조한다.
- 신규 Runtime 경계 테스트는 기존 hotspot test class를 키우지 않도록 전용 `test_*.py` 모듈에 둔다.
- migration은 필요하지 않다.

## 실행 단계
- [x] Observer 공개 조회 기간 계약을 추가하고 serializer와 Assistant Runtime을 정합화한다.
- [x] 32일·90일 허용과 91일 거부 테스트를 추가한다.
- [x] Assistant 테스트와 migration·backend boundary 검증을 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml run --rm --no-deps --entrypoint python api manage.py test api.assistant.test_observer_analysis_range`
- `docker compose -f docker-compose.dev.yml run --rm --no-deps --entrypoint python api manage.py test api.common api.assistant api.observer`
- `docker compose -f docker-compose.dev.yml run --rm --no-deps --entrypoint python api manage.py makemigrations --check --dry-run`
- `npm run agent:audit`
- 기대 결과: 화면의 모든 정상 조회 범위는 분석되고 91일 이상 요청만 명확한 오류로 거부된다.

## 위험과 대응
- 위험: 분석 기간 확대로 조회 데이터와 OpenWebUI 입력 생성 비용이 증가할 수 있다.
- 대응: 기존 Observer 분석의 source별 5,000건 및 prompt 문자 예산을 유지하고 화면과 동일한 90일 상한을 둔다.

## 진행 기록
- 2026-08-14: 별도 31일 제한을 제거하고 Observer 화면과 동일한 최대 90일 계약으로 맞추기로 했다.
- 2026-08-14: Observer serializer와 Assistant Runtime이 같은 backend 공개 상수를 사용하도록 중복 계약을 제거했다.
- 2026-08-14: 전용 경계 테스트와 관련 backend 테스트 141건, migration check 및 전체 agent audit 통과를 확인했다.
