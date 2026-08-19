# ExecPlan: Data Movement `ct_process_comment`

## 목표
- comment incremental upsert와 OpenWebUI summary lifecycle, Observer 소비와 Airflow DAG를 명확히 분리한다.

## 현재 상태
- control-character `0x03` delimiter 17-column 파일을 `workorder_id`로 upsert한다.
- ctttm workorder 존재, E-prefix eqp, `use_yn != N`만 적재하고 내용 변경 시 summary retry state를 갱신한다.
- summary service 1,248줄, tests 1,724줄이며 API DAG 외에 DB를 직접 읽는 연속 요약 DAG가 있다.

## 범위
- 수정: loader/spec/selectors/summary services/tests/commands, 두 summary DAG, Observer adapter, docs/env.
- 유지: workorder 선행 dependency, summary/core-summary/retry semantics, OpenWebUI provider와 failure fallback.

## 설계
- loader는 `workorder_id` 변경 감지 upsert와 `updateFlag`/summary reset을 transaction에서 수행한다.
- summary를 candidate selection, prompt, streaming parser, row transition, batch orchestration module로 분리한다.
- API request/response는 `dryRun`, `processedCount`, `skippedCount`, `dryRunCount` 등 camelCase를 사용한다.
- 모든 row 실패일 때만 500인 현재 partial-success 규칙을 유지한다.
- 연속 요약 DAG의 직접 DB read는 selector/API contract로 교체해 Airflow가 table schema를 소유하지 않게 한다.
- schema는 유지하고 migration은 없다.

## 실행 단계
- [x] loader change-detection과 summary state machine characterization을 고정한다.
- [x] loader를 공통 lifecycle에 연결한다.
- [x] summary service/test hotspot을 책임별 package/class로 분리한다.
- [x] 두 DAG를 canonical API 계약으로 통합한다.
- [x] Observer CTTTM detail과 docs/env를 검증한다.

## 검증
- dev API container에서 `api.data_movement.ct_process_comment api.observer` tests.
- Airflow summary tests와 DAG import.
- partial/all failure, timeout, retry cap, unchanged content, transaction rollback tests.

## 위험과 대응
- 위험: summary 상태 전이가 재요약을 누락하거나 무한 재시도한다.
- 대응: 각 terminal/transient 상태와 retry count transition table test를 둔다.
- 위험: 직접 DB DAG 제거가 처리량을 낮춘다.
- 대응: API batch size와 cursor를 기존 batch cardinality로 맞추고 실행 시간 비교를 기록한다.

## 의존성과 복구
- 상위 계약: [마스터](repository-refactor-master-2026-08.md), [Data Movement 공통](data-movement-common-refactor.md), [`ctttm_workorder_list`](data-movement-ctttm-workorder-list-refactor.md), 후행 RAG/Observer 계획.
- 복구: loader/summary/DAG를 함께 revert한다. comment 원문은 보존하고 잘못된 summary state만 사전 backup 또는 load-job/source 기준으로 복원한 뒤 재요약한다.

## 진행 기록
- 2026-08-18: 직접 DB DAG를 제거하고 API/service가 schema를 소유하도록 확정했다.
- 2026-08-18: 17단계를 완료했다. loader를 공통 runner/command에 연결하고 prompt/constants를 summary orchestration에서 분리했으며 summary 테스트를 응답·핵심요약·상태·loader 책임으로 나눴다. 540줄 연속 DAG의 DB/OpenWebUI 직접 구현을 107줄 canonical API consumer로 교체했다. ct_process_comment 56개·Observer 포함 133개·Airflow 3개 테스트와 hotspot 감사를 통과했고 summary/file/class baseline 3건을 제거했다.
