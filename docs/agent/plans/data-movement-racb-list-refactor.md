# ExecPlan: Data Movement `racb_list`

## 목표
- RACB 최신 row 선택, 설비 explode, 범위 교체와 Observer URL 계약을 실제 코드 기준으로 정리한다.

## 현재 상태
- 실제 spec/loader/test는 백틱 delimiter를 사용하지만 API 문서는 comma delimiter라고 잘못 적혀 있다.
- MEMORY·ETCH row만 남기고 `c_racb_id`별 최신 `update_date`를 고른 뒤 comma-separated `eqp_ids`를 explode한다.
- `(c_racb_id, eqp_cb)` unique이며 Observer가 selector facade를 소비한다.

## 범위
- 수정: spec/loader/selectors/tests/command, Observer RACB adapter, `RACB_REPORT_BASE_URL` env/docs.
- 유지: 백틱 row delimiter, `eqp_ids` 내부 comma split, latest 기준, 범위 교체와 stable ID.

## 설계
- 문서를 실제 source contract인 백틱 delimiter로 수정한다. `eqp_ids` field 내부에서만 comma를 separator로 사용한다.
- 동일 `c_racb_id`의 최신 row를 선택하고 해당 id의 기존 explode rows를 transaction에서 전부 교체한다.
- required create/update datetime과 non-empty id/eqp를 검증한다.
- report URL은 env가 비어 있으면 payload에서 `url`을 null로 반환하고 하드코딩 fallback을 사용하지 않는다.
- schema/migration 변화는 없다.

## 실행 단계
- [x] delimiter/latest/filter/explode characterization을 고정한다.
- [x] 공통 lifecycle에 연결하고 범위 교체를 유지한다.
- [x] Observer page/detail/URL payload를 검증한다.
- [x] stale docs/env example을 갱신한다.

## 검증
- dev API container에서 `api.data_movement.racb_list api.observer` tests.
- 백틱 원천, comma eqp list, duplicate latest, empty URL, rollback test.

## 위험과 대응
- 위험: delimiter 오해로 정상 파일이 1-column으로 읽힌다.
- 대응: exact 31-column width와 실 source-shaped fixture를 둔다.

## 의존성과 복구
- 상위 계약: [마스터](repository-refactor-master-2026-08.md), [Platform Common](platform-common-health-errors-refactor.md), [Data Movement 공통](data-movement-common-refactor.md). Observer RACB timeline의 선행 단계다.
- 복구: loader/selector/env를 revert하고 영향 `c_racb_id`를 source file이나 사전 backup에서 재적재한다.

## 진행 기록
- 2026-08-18: 코드/test의 백틱 계약을 canonical로 선택하고 문서 drift 수정을 확정했다.
- 2026-08-18: 14단계를 완료했다. 원천 백틱/필드 내부 comma 계약을 문서와 일치시키고 latest/explode 범위 교체를 공통 runner/command에 연결했다. 하드코딩된 기본 report URL을 비우고 비활성 URL을 null로 통일했으며 Observer 포함 85개 테스트가 통과했다.
