# ExecPlan: Data Movement `eqp_status_chg`

## 목표
- 설비 상태 변경 incremental upsert와 Observer timeline 시간 계약을 보존하면서 loader를 공통 규약에 맞춘다.

## 현재 상태
- 백틱 11-column 파일, `eqp_event_key` unique upsert, E/e 설비 filter와 180일 retention을 사용한다.
- timezone 없는 `chg_time`, `last_update_time`을 KST 벽시계로 해석해 UTC로 저장한다.

## 범위
- 수정: spec/loader/selectors/tests/command, Observer 소비 test와 문서.
- 유지: table/unique/indexes, KST 해석, retention, stable event ID와 timeline payload.

## 설계
- source cutoff는 KST wall-clock, DB purge cutoff는 같은 instant의 UTC로 계산한다.
- 파일 안 같은 event key는 마지막 유효 row로 정규화하고 temp COPY 후 `ON CONFLICT(eqp_event_key)` upsert를 수행한다.
- 잘못된 datetime/key는 파일 전체 실패로 처리하며 기존 row와 retention purge를 모두 롤백한다.
- schema/migration 변화는 없다. 적용된 timezone 보정 migration은 수정하지 않는다.

## 실행 단계
- [x] timezone/filter/dedup/upsert/retention characterization을 고정한다.
- [x] 공통 runner에 policy를 연결한다.
- [x] Observer page/detail/cursor contract를 검증한다.
- [x] 공통 command와 canonical API summary를 검증한다.

## 검증
- dev API container에서 `api.data_movement.eqp_status_chg api.observer` tests.
- KST/UTC boundary, 180-day edge, rollback, unique/index query plan test.

## 위험과 대응
- 위험: cutoff 계산 drift로 9시간 범위가 사라진다.
- 대응: 경계 직전/직후 fixture와 저장 instant를 고정한다.

## 의존성과 복구
- 상위 계약: [마스터](repository-refactor-master-2026-08.md)와 [Data Movement 공통](data-movement-common-refactor.md). Observer EQP timeline의 선행 단계다.
- 복구: loader/selector 코드를 revert하고 잘못 반영된 key는 load-job source file로 재적재한다. retention으로 제거된 row 복구는 사전 DB backup을 사용한다.

## 진행 기록
- 2026-08-18: KST source/UTC storage 계약을 불변으로 확정했다.
- 2026-08-18: 11단계를 완료했다. KST/UTC·180일 retention·event-key upsert transaction을 유지하며 공통 runner/command에 연결했고 Observer 포함 87개 테스트가 통과했다.
