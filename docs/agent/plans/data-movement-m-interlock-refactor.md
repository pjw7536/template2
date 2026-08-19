# ExecPlan: Data Movement `m_interlock`

## 목표
- interlock 증분 적재의 중복 처리와 Observer SPC/FDC 소비 계약을 명시적으로 고정한다.

## 현재 상태
- header 없는 백틱 35-column 파일을 읽고 `interlock_no`로 upsert한다.
- 빈 key는 제외하고 파일 내 중복은 마지막 row를 사용하며 lookup 파생 field를 같은 transaction에서 갱신한다.

## 범위
- 수정: spec/loader/selectors/tests/command와 Observer interlock adapter test.
- 유지: table, unique key, numeric/text precision, retention 없음, SPC/FDC 두 Observer source.

## 설계
- filename의 line/timestamp와 row line_id 일치는 검증하되 업무 row의 원천 line_id를 보존한다.
- dedup ordering은 파일 순서의 마지막 row, 기존 DB 정리 기준은 `last_update_date DESC, id DESC`로 유지한다.
- `prod_eqp_id_lookup`, `interlock_kind_lookup`, `prod_progs_at` 파생값은 upsert row와 원자적으로 저장한다.
- invalid width/datetime은 파일 전체 실패로 처리한다.
- schema/migration 변화는 없다.

## 실행 단계
- [x] 35-column/key/dedup/lookup characterization을 고정한다.
- [x] 공통 lifecycle/COPY에 연결한다.
- [x] SPC/FDC page/detail payload와 index 사용을 검증한다.
- [x] 공통 command와 canonical API/DAG 계약을 검증한다.

## 검증
- dev API container에서 `api.data_movement.m_interlock api.observer` tests.
- duplicate/blank key, unbounded numeric/lot text, transaction rollback test.

## 위험과 대응
- 위험: dedup 기준 변경으로 최신 업무 row가 바뀐다.
- 대응: source order와 DB legacy duplicate 정리 규칙을 별도 fixture로 고정한다.

## 의존성과 복구
- 상위 계약: [마스터](repository-refactor-master-2026-08.md)와 [Data Movement 공통](data-movement-common-refactor.md). Observer SPC/FDC timeline의 선행 단계다.
- 복구: loader/selector를 revert하고 영향 `interlock_no`를 source file 또는 사전 backup에서 재적재한다. retention이 없어 비영향 row는 그대로 유지한다.

## 진행 기록
- 2026-08-18: retention 없는 key upsert와 두 Observer adapter를 확정했다.
- 2026-08-18: 12단계를 완료했다. 35-column·마지막 중복·blank key·lookup upsert 정책을 보존하며 공통 runner에 연결했고 Observer 포함 98개 테스트가 통과했다.
