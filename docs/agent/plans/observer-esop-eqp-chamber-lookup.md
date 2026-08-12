# ExecPlan: Observer ESOP EQP·챔버 lookup 복구

## 목표
- POP3로 적재된 ESOP 행이 Observer의 `설비-챔버` 선택값과 안정적으로 매칭되게 한다.
- `chamber_ids="ABC"` 행은 같은 설비의 `A`, `B`, `C` 챔버 조회에 각각 표시되게 한다.

## 현재 상태
- Observer ESOP compact page와 detail은 `DroneSOP.eqp_id_lookup`을 정확히 비교한다.
- POP3 raw SQL upsert는 `eqp_id_lookup`을 INSERT/UPDATE하지 않아 신규 행에 NULL이 남을 수 있다.
- 기존 legacy ESOP selector에는 `설비-챔버` 분리 로직이 있지만 compact page selector에는 적용되지 않는다.
- `apps/api/api/observer/tests.py`에는 사용자 작업이 있으므로 이번 변경에서 수정하지 않는다.

## 범위
- 수정: `api.drone` POP3 persistence, Observer용 DroneSOP selector, Drone 테스트.
- 추가: 기존 `eqp_id_lookup` 누락·불일치를 보정하는 새 data migration.
- 제외: API response shape, frontend, auth/permission, DB schema/index 변경, 다른 Observer 로그 유형.

## 설계
- `eqp_id_lookup`은 대문자·trim 처리한 기본 설비 ID를 유지한다.
- Observer 입력은 첫 `-`를 설비/챔버 경계로 해석하고, 챔버 suffix의 각 문자를 중복 제거한 후보로 사용한다.
- ESOP page/detail은 기본 설비 lookup과 날짜/source ID를 먼저 제한한 뒤 `chamber_ids`가 후보 중 하나를 포함하는지 확인한다.
- POP3 raw SQL upsert는 `eqp_id_lookup`을 명시적으로 dual-write한다.
- 새 migration은 NULL뿐 아니라 원본 `eqp_id`와 불일치하는 lookup도 멱등적으로 보정한다.
- public API/facade, env, auth 계약에는 영향이 없다.

## 실행 단계
- [x] POP3 upsert에 `eqp_id_lookup` 정규화와 INSERT/UPDATE를 추가한다.
- [x] compact page/detail selector에 EQP·챔버 매칭을 추가한다.
- [x] 기존 lookup을 보정하는 새 data migration을 추가한다.
- [x] 신규 INSERT·기존 NULL 복구·ABC 챔버 매칭 회귀 테스트를 추가한다.
- [x] Docker Compose `api` 컨테이너에서 관련 테스트와 migration 검증을 수행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.drone.tests.DroneSopUpsertTests api.drone.tests.DroneSopObserverSelectorTests --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate --plan`
- `npm run agent:audit:api-boundary`
- 기대 결과: raw upsert 행의 lookup이 채워지고 `EQP01-A/B/C`는 조회되며 `EQP01-D`는 제외된다.

## 위험과 대응
- 위험: 챔버 없는 설비 조회에서 기존 전체 챔버 표시가 바뀔 수 있다.
- 대응: `-`가 없는 입력은 기본 설비의 모든 챔버를 유지한다.
- 위험: 대량 backfill이 운영 DB write 부하를 만들 수 있다.
- 대응: 불일치 행만 UPDATE하고 배포 시 POP3 적재와 migration 실행이 겹치지 않게 한다.
- 위험: 사용자 작업 중인 Observer 테스트와 충돌할 수 있다.
- 대응: 변경과 테스트를 `api.drone` 소유 파일에 한정한다.

## 진행 기록
- 2026-08-12: `-`는 항상 설비/챔버 구분자이고 연속 챔버 문자열은 문자별 챔버라는 계약을 확정했다.
- 2026-08-12: POP3 lookup dual-write, 기존 데이터 backfill, compact page/detail 챔버 매칭과 회귀 테스트를 구현했다.
- 2026-08-12: Drone·Observer 370건, migration check/apply, backend boundary audit, diff 무결성 검증이 통과했다.
